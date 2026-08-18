# Lane C · publish/ 发布通道层（小红书+抖音表单 + 人工确认闸） · 积木④

**分派对象**: exec-strong
**积木**: ④ publish（发布通道层）
**轮次**: 第 2 轮（依赖 Lane A 的 `AbstractBrowserEngine` / `UnittestEngine` 接口契约，与 Lane B 的 `CookieStore` / `AccountManager` 接口）
**前置依赖**: Lane A（engine.py）+ Lane B（cookie_store.py / account_manager.py）已 push 到 origin/main
**产出**: `marketing-agent/publish/` 目录完整

---

## 0. 任务是什么

1. **小红书表单填料**：按小红书发布页字段结构，调 `AbstractBrowserEngine` 接口填表
2. **抖音表单填料**：按抖音发布页字段结构，调 `AbstractBrowserEngine` 接口填表
3. **人工确认闸**：填完后生成预览 → 等待人工确认 → 点发布按钮
4. 全部用 `UnittestEngine` 测试（不依赖真实浏览器，参照 M004 教训）

## 1. 文件清单

| 文件 | 说明 |
|------|------|
| `marketing-agent/publish/__init__.py` | 包初始化 |
| `marketing-agent/publish/platforms/__init__.py` | 平台子包初始化 |
| `marketing-agent/publish/platforms/xiaohongshu.py` | 小红书发布表单（标题/正文/图片/标签/定时） |
| `marketing-agent/publish/platforms/douyin.py` | 抖音发布表单（标题/视频/封面/话题/定时） |
| `marketing-agent/publish/human_gate.py` | 人工确认闸（预览→确认→发布指令） |
| `marketing-agent/publish/tests/__init__.py` | 测试包初始化 |
| `marketing-agent/publish/tests/test_xiaohongshu.py` | 小红书表单测试 |
| `marketing-agent/publish/tests/test_douyin.py` | 抖音表单测试 |
| `marketing-agent/publish/tests/test_human_gate.py` | 人工确认闸测试 |

## 2. 接口契约（冻结）

### 2.1 publish/platforms/xiaohongshu.py

```python
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

@dataclass
class XhsPost:
    """小红书发布内容。"""
    title: str  # 标题（≤20字）
    body: str  # 正文
    tags: List[str] = field(default_factory=list)  # 话题标签（≤5个）
    images: List[Path] = field(default_factory=list)  # 图片路径（1-9张）
    schedule_time: Optional[str] = None  # 定时发布时间（ISO 8601），None=立即
    location: Optional[str] = None  # 地点

class XhsPublisher:
    """小红书发布器。需注入 AbstractBrowserEngine 实例。"""

    def __init__(self, engine):
        self.engine = engine

    def fill_form(self, post: XhsPost) -> dict:
        """将 XhsPost 内容填入小红书发布表单。
        返回发布前的预览摘要 dict（标题/正文摘要/标签/图数/定时）。"""

    def publish(self) -> None:
        """点击「发布」按钮。调用前必须先 fill_form()。
        真实发布：engine.click("#publish-btn")。"""

    def validate(self, post: XhsPost) -> List[str]:
        """校验发布内容。返回违规列表，空列表=通过。
        校验规则：
        - 标题非空，≤20 字
        - 正文非空
        - 标签 ≤5 个
        - 图片 1-9 张
        - 不含禁用词（调用合规闸 L1 快速检查——可选集成）"""
```

### 2.2 publish/platforms/douyin.py

```python
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

@dataclass
class DyPost:
    """抖音发布内容。"""
    title: str  # 视频描述（≤55字）
    video_path: Path  # 视频文件路径
    cover_path: Optional[Path] = None  # 封面图路径
    topics: List[str] = field(default=list)  # 话题标签（≤5个）
    schedule_time: Optional[str] = None  # 定时发布时间
    location: Optional[str] = None  # 地点

class DyPublisher:
    """抖音发布器。需注入 AbstractBrowserEngine 实例。"""

    def __init__(self, engine):
        self.engine = engine

    def fill_form(self, post: DyPost) -> dict:
        """将 DyPost 内容填入抖音发布表单。
        返回发布前的预览摘要 dict。"""

    def publish(self) -> None:
        """点击「发布」按钮。"""

    def validate(self, post: DyPost) -> List[str]:
        """校验发布内容。返回违规列表，空列表=通过。
        - 标题非空，≤55 字
        - video_path 非 None
        - 话题 ≤5 个"""
```

### 2.3 publish/human_gate.py

```python
from dataclasses import dataclass
from typing import Optional, Callable, Dict
from enum import Enum

class GateDecision(Enum):
    CONFIRM = "confirm"  # 人工确认发布
    ABORT = "abort"  # 取消发布
    EDIT = "edit"  # 返回编辑

@dataclass
class GateResult:
    decision: GateDecision
    reason: str = ""
    edited_fields: Optional[Dict] = None

class HumanGate:
    """人工确认闸。半自动发布流程的最后一道防线。

    流程：
    1. generate_preview() → 生成预览摘要
    2. request_confirm() → 等待人工输入
    3. 按 decision 执行：CONFIRM → 发布 / ABORT → 取消 / EDIT → 返回编辑
    """

    def __init__(self,
                 input_fn: Optional[Callable[[str], str]] = None):
        """input_fn: 获取用户输入的回调函数。用于测试注入。
        None 时使用内置 input()。"""

    def generate_preview(self, platform: str, post_summary: dict) -> str:
        """生成发布预览文本。包含平台/标题/正文摘要/标签/图数/定时/合规状态。"""

    def request_confirm(self, preview: str) -> GateResult:
        """展示预览文本，等待人工输入确认。
        输入: "Y/y/yes" → CONFIRM, "N/n/no" → ABORT, "E/e/edit" → EDIT。
        测试时通过 input_fn 注入模拟输入。"""

    def is_auto_publish_disabled(self) -> bool:
        """纯 API 签名发布禁用检查。始终返回 True（架构红线）。"""
        return True
```

## 3. 验收标准

### xiaohongshu.py
- [ ] `XhsPublisher.fill_form()` 注入 UnittestEngine 后，引擎 ops 包含 "navigate" + "fill_form" 操作
- [ ] `XhsPublisher.validate()` 空标题返回 ["标题不能为空"]
- [ ] `XhsPublisher.validate()` 标题 >20 字返回 ["标题不能超过20字"]
- [ ] `XhsPublisher.validate()` 6 个标签返回 ["标签不能超过5个"]
- [ ] `XhsPublisher.validate()` 合法内容返回空列表
- [ ] `XhsPublisher.publish()` 在 fill_form 后调用，引擎 ops 包含 "click"

### douyin.py
- [ ] `DyPublisher.fill_form()` 注入 UnittestEngine 后，引擎 ops 包含 "navigate" + "fill_form" 操作
- [ ] `DyPublisher.validate()` 标题 >55 字返回违规
- [ ] `DyPublisher.validate()` video_path 为 None 时返回违规
- [ ] `DyPublisher.validate()` 合法内容返回空列表

### human_gate.py
- [ ] `HumanGate.generate_preview()` 返回包含平台/标题/标签的预览文本
- [ ] `HumanGate.request_confirm()` 注入 "Y" → CONFIRM
- [ ] `HumanGate.request_confirm()` 注入 "N" → ABORT
- [ ] `HumanGate.request_confirm()` 注入 "E" → EDIT
- [ ] `HumanGate.request_confirm()` 注入无效输入 → 重试（至少一次）
- [ ] `HumanGate.is_auto_publish_disabled()` 始终返回 True

## 4. 测试要求

- 至少 15 个测试（xhs: 5 + dy: 4 + human_gate: 6）
- 全部使用 UnittestEngine（不依赖 playwright）
- 测试独立运行：`python -m pytest publish/tests/ -v`
- 全绿，无假绿

## 5. ⚠️ 历史同类坑（必读）

1. **M001/M-L002 路径硬编码**：从 `marketing-agent/browser/engine.py` import 用 `from ..browser.engine import ...` 相对导入，不写死绝对路径
2. **M004/M-L004 预览不送门**：`human_gate.py` 的 `generate_preview()` 只是预览摘要，不调质量/合规门。真稿审核由上游流水线负责
3. **M005/M-L003 Windows GBK**：`human_gate.py` 打印预览文本用纯 ASCII 或标记，不打印 emoji；测试用 `PYTHONIOENCODING=utf-8`
4. **M002/M-L001 仓库根**：commit 从 `D:/llm/marketing-agent/` 跑，不是 `marketing-agent/` 子目录
5. **依赖链**：Lane C 依赖 Lane A 的 `AbstractBrowserEngine`/`UnittestEngine` 接口。开始前确认 `git pull origin master` 获取最新，确认 `browser/engine.py` 存在。如果 A 未完成，用临时 stub 替代（但最终必须对齐）

## 6. 交付格式

产出 `docs/evidence/DAY2-C-PACKET.md`，四节：
1. 完成概况
2. 测试结果
3. 文件清单
4. 自查证据（逐条验收标准 PASS/FAIL）

**禁止**：第 4 节为空、夹带积木①②③ 或 browser/ 的文件修改（publish/ 只消费 browser 接口，不改 browser 代码）、不使用 UnittestEngine 做测试。