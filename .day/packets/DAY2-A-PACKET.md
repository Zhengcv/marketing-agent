# Lane A · browser/engine.py + browser/humanize.py · 积木⑤ 反检测底座（引擎抽象+真人行为）

**分派对象**: exec-strong
**积木**: ⑤ browser（反检测底座）
**轮次**: 第 1 轮（无依赖，独立）
**产出**: `marketing-agent/browser/engine.py`, `marketing-agent/browser/humanize.py`, 测试

---

## 0. 任务是什么

创建反检测底座的**引擎抽象层**和**真人行为模拟器**。不做真实浏览器操作（无账号/代理/密钥），只定义接口契约 + 可离线验证的算法。

## 1. 文件清单

| 文件 | 说明 |
|------|------|
| `marketing-agent/browser/__init__.py` | 包初始化，导出公共符号 |
| `marketing-agent/browser/engine.py` | AbstractBrowserEngine 抽象基类 + UnittestEngine + engine_factory |
| `marketing-agent/browser/humanize.py` | 贝塞尔鼠标路径 + 真人键盘输入 + 随机停留 |
| `marketing-agent/browser/tests/__init__.py` | 测试包初始化 |
| `marketing-agent/browser/tests/test_engine.py` | 引擎工厂与抽象接口测试 |
| `marketing-agent/browser/tests/test_humanize.py` | 真人行为函数测试 |

## 2. 接口契约（冻结）

### 2.1 engine.py — AbstractBrowserEngine

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class BrowserConfig:
    headless: bool = True
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    viewport: dict = field(default_factory=lambda: {"width": 1280, "height": 800})
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"
    extra_args: dict = field(default_factory=dict)

class AbstractBrowserEngine(ABC):
    """浏览器引擎抽象接口。所有具体引擎（invisible_playwright / patchright）必须实现此接口。"""

    @abstractmethod
    def initialize(self, config: BrowserConfig) -> None:
        """启动浏览器实例，应用反指纹配置。"""
        ...

    @abstractmethod
    def navigate(self, url: str) -> None:
        """导航到指定 URL。"""
        ...

    @abstractmethod
    def fill_form(self, fields: dict) -> None:
        """按 selector → value 字典填入表单。"""
        ...

    @abstractmethod
    def click(self, selector: str) -> None:
        """点击元素。"""
        ...

    @abstractmethod
    def screenshot(self, path: str) -> None:
        """截取全页截图，保存到 path。"""
        ...

    @abstractmethod
    def save_storage_state(self, path: str) -> None:
        """保存当前浏览器登录态（cookies + localStorage）到 JSON 文件。"""
        ...

    @abstractmethod
    def load_storage_state(self, path: str) -> None:
        """从 JSON 文件恢复浏览器登录态。"""
        ...

    @abstractmethod
    def close(self) -> None:
        """关闭浏览器实例。"""
        ...


class UnittestEngine(AbstractBrowserEngine):
    """测试用空实现，所有方法记录操作日志但不启动真实浏览器。"""

    def __init__(self):
        self.ops: list[dict] = []
        self._storage_state: Optional[dict] = None

    # 所有方法记录 ops 列表，方便测试验证调用顺序


class PlaywrightEngine(AbstractBrowserEngine):
    """invisible_playwright 适配器。TODO: 真机环境安装 playwright 后补全。"""

    def __init__(self):
        self._browser = None
        self._page = None
        self._playwright = None

    # TODO: 真机环境补全。本地测试用 UnittestEngine 替代。


def engine_factory(name: str = "unittest") -> AbstractBrowserEngine:
    """工厂方法，返回指定引擎实例。
    - "unittest" → UnittestEngine（离线测试默认）
    - "playwright" → PlaywrightEngine（需 pytest --integration）
    """
```

### 2.2 humanize.py — 真人行为模拟

```python
from typing import List, Tuple, Dict

def generate_bezier_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    steps: int = 30,
    jitter: float = 3.0
) -> List[Tuple[float, float]]:
    """生成贝塞尔曲线鼠标移动路径。control_point 随机偏移产生自然弯曲。"""

def human_type(
    text: str,
    wpm: int = 60,
    error_rate: float = 0.02
) -> List[Dict]:
    """逐字真人键盘输入。返回每键的 {char, delay_ms, corrected} 记录。
    模拟偶尔打错→退格→修正（error_rate 概率）。"""

def random_pause(min_ms: int = 200, max_ms: int = 3000) -> float:
    """生成随机停留时间（ms），对数正态分布，偏向短停留。"""

def mouse_jitter(position: Tuple[int, int], amplitude: int = 2) -> Tuple[int, int]:
    """在给定位置附近添加微小抖动。"""
```

## 3. 验收标准

### engine.py
- [ ] `engine_factory("unittest")` 返回 UnittestEngine 实例
- [ ] `engine_factory("playwright")` 返回 PlaywrightEngine 实例
- [ ] `engine_factory("unknown")` 抛出 ValueError
- [ ] UnittestEngine 所有 8 个方法调用后 ops 列表记录正确操作名
- [ ] PlaywrightEngine 实例化不抛异常（不 import playwright，惰性初始化）
- [ ] BrowserConfig 默认值正确（headless=True, locale="zh-CN", timezone="Asia/Shanghai"）

### humanize.py
- [ ] `generate_bezier_path((0,0), (100,100), 30)` 返回 30 对坐标，首尾正确
- [ ] 贝塞尔路径不包含直线段（control_point 随机偏移产生弯曲）
- [ ] `human_type("hello", wpm=60, error_rate=0)` 返回 list of dict，每键有 char/delay_ms/corrected
- [ ] `human_type("hello", wpm=60, error_rate=1.0)` 每键都标记 corrected=True（概率边界）
- [ ] `random_pause(200, 3000)` 返回 float 在 [200, 3000] 范围内
- [ ] `mouse_jitter((100, 100), 2)` 返回的坐标偏移在 [-2, 2] 范围内

## 4. 测试要求

- 至少 12 个测试（engine: 6 + humanize: 6）
- 测试独立运行：`python -m pytest browser/tests/ -v`
- 全绿，无假绿（不能用 `pytest.skip` 或空 `pass` 充数）
- UnittestEngine 不依赖任何外部库（playwright 等），可离线跑

## 5. ⚠️ 历史同类坑（必读，重犯即打回）

1. **M001/M-L002 路径硬编码**：`BASE_DIR = Path(__file__).resolve().parent` 推导，所有路径用仓库根相对路径，禁止写死 `docs/marketing/...` 中间层目录名
2. **M005/M-L003 Windows GBK**：`__init__.py` 或 CLI 入口第一行 `_ensure_utf8_stdout()`；测试用 `PYTHONIOENCODING=utf-8`
3. **M002/M-L001 仓库根**：commit 前必须 `git -C D:/llm/marketing-agent rev-parse --show-toplevel` 确认，禁止在 `marketing-agent/` 子目录跑 git add
4. **M004/M-L004 预览不送门**：UnittestEngine 是离线测试桩，不触发真浏览器，不送质量/合规门

## 6. 交付格式

产出 `docs/evidence/DAY2-A-PACKET.md`，四节：
1. 完成概况（做了什么，文件清单）
2. 测试结果（pytest 输出截屏/粘贴）
3. 文件清单（新建/修改的文件完整路径）
4. 自查证据（自己跑一遍验收标准，逐条标注 PASS/FAIL）

**禁止**：第 4 节为空、夹带积木①②③ 的文件修改、跳过 workbook 建目录步骤。