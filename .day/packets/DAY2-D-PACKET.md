# Lane D · rate_limit.py + sqlite.py + run.py 入口 · 积木④ 发布通道（调度+频控）

**分派对象**: exec-luna
**积木**: ④ publish（发布通道层）— 调度 + 频控后端
**轮次**: 第 2 轮（依赖 Lane A + Lane B 的接口契约，与 Lane C 并行）
**前置依赖**: Lane A（engine.py）+ Lane B（cookie_store.py / account_manager.py）已 push 到 origin/main
**产出**: `marketing-agent/publish/rate_limit.py`, `marketing-agent/publish/storage.py`, `marketing-agent/publish/run.py`, `marketing-agent/publish/tests/test_rate_limit.py`, `marketing-agent/publish/tests/test_storage.py`

---

## 0. 任务是什么

1. **发布记录 SQLite**：存储每次发布（时间/平台/账号/内容摘要/结果）
2. **频控**：每天 ≤1 篇/账号，间隔 24h 硬约束
3. **CLI 入口 run.py**：半自动发布流程编排（内容→合规→填表→预览→人工确认→回写），默认 dry-run/browser=tests 不发真平台
4. **事件钩子**：预留 mock 注入点（让 .day-go 或集成测试可以插入 fake publisher）

## 1. 文件清单

| 文件 | 说明 |
|------|------|
| `marketing-agent/publish/__init__.py` | 包初始化 |
| `marketing-agent/publish/storage.py` | SQLite 发布记录（增查/最近发布时间） |
| `marketing-agent/publish/rate_limit.py` | 频控（24h 间隔 / 每日1篇） |
| `marketing-agent/publish/run.py` | CLI 入口：编排半自动发布流程（dry-run 默认） |
| `marketing-agent/publish/tests/test_rate_limit.py` | 频控测试 |
| `marketing-agent/publish/tests/test_storage.py` | 存储测试 |

## 2. 接口契约（冻结）

### 2.1 rate_limit.py

```python
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class RateLimitResult:
    allowed: bool
    reason: str  # 允许时 "ok"，拒绝时说明
    next_allowed_at: Optional[float]  # 下次允许时间戳

class RateLimiter:
    def __init__(self, storage):  # storage: PublishRecordStore
        self._storage = storage

    def check(self, platform: str, account_id: str, now: Optional[float] = None) -> RateLimitResult:
        """检查是否允许该账号在 now 时刻发布。
        now 默认 time.time()。
        规则：距上次发布 < 24h → 拒绝；否则允许。"""

    def config_daily_unit(self) -> int:
        """返回每日发布上限 = 1（架构红线，硬编码常量）。"""

    def next_allowed_at(self, platform: str, account_id: str, now: Optional[float] = None) -> float:
        """返回该账号下次允许发布的时刻。"""
```

### 2.2 storage.py （或放 publish/storage.py）

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import sqlite3

@dataclass
class PublishRecord:
    id: int
    platform: str
    account_id: str
    content_hash: str  # 内容摘要哈希（防重复）
    status: str  # "pending" | "published" | "aborted"
    created_at: float
    published_at: Optional[float]

class PublishRecordStore:
    """SQLite 发布记录存储。"""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """建表 if not exists。"""

    def add_pending(self, platform: str, account_id: str, content_hash: str) -> int:
        """新增一条 pending 发布记录，返回 id。"""

    def mark_published(self, record_id: int, published_at: Optional[float] = None) -> None:
        """标记记录为 published。"""

    def mark_aborted(self, record_id: int) -> None:
        """标记记录为 aborted（人工取消/失败）。"""

    def latest_published_time(self, platform: str, account_id: str) -> Optional[float]:
        """返回该账号最近一次 published 的时间戳，未发布过返回 None。"""

    def count_published_today(self, platform: str, account_id: str, today_start: float) -> int:
        """返回该账号从 today_start 之后发布的次数（每日1篇红线）。"""
```

### 2.3 run.py — CLI 入口（mock 模式，不发真平台）

```python
"""
半自动发布流程命令行入口。

用法（默认 dry-run，不发真平台）:
    python -m publish.run --platform xiaohongshu --account acct_01 \
        --title "标题" --body "正文" --tags 标签1 标签2 [--mock]

注入点：为测试/演示，支持 --publisher-stub 环境或参数覆盖 AbstractBrowserEngine / Publisher 实现，
默认使用 UnittestEngine 的 mock publisher。真实平台发布请在真机配好 playwright 后手动启用。
"""
```

- **默认不真正发布**（只打印预览 + 走人工确认闸，最终点确认也只是打日志）
- 必须校验频控：`RateLimit.check()` 不过 → 拒绝并打印原因
- 必须校验合规：简单集成 compliance/check（复用积木③，若未集成则跳过并提示）
- 必须校验质量：可选集成 quality/（M004 教训：预览文件跳过）

## 3. 验收标准

### rate_limit.py
- [ ] `config.rate_limit_hours` 默认 24
- [ ] `constraint.daily_max=1`
- [ ] `constraint.min_interval_hours=24`
- [ ] `RateLimit.check()` 从未发布返回 allowed=True
- [ ] `RateLimit.check()` 距上次 <24h 返回 allowed=False, reason 含 "间隔"
- [ ] `RateLimit.check()` 距上次 ≥24h 返回 allowed=True

### storage.py
- [ ] `PublishRecordStore.mark_published()` 正确更新数据库
- [ ] `latest_published_time()` 未发布返回 None
- [ ] `latest_published_time()` 有发布返回时间戳
- [ ] `count_published_today()` 统计正确
- [ ] SQLite 文件创建成功（tempfile 目录）

### run.py
- [ ] 命令行解析成功（`--platform`/`--account`/`--title`/`--content` 参数）
- [ ] 默认 dry-run 不发真平台（只打印预览）
- [ ] 唯一能触发真实发布的且明确 `--live` 不可用（返回错误，提示人工发布）
- [ ] 频控拒绝时打印清晰提示

## 4. 测试要求
- 至少 12 个测试（`storage: 5 + rate_limit: 5 + run: 2`）
- 存储测试用 tempfile, 测后清理。
- `python -m pytest publish/tests/ -v` 全绿
- **run.py 默认 dry-run 绝对不可触发真实平台发布**

## 5. 历史坑（重犯即打回）
- **M001/M-L002 路径**：不写死中间层目录；`BASE_DIR` 用 `Path(__file__).resolve().parent` 推导。
- **M002/M-L001 仓库根**：commit 前 `git -C D:/llm/marketing-agent rev-parse --show-toplevel`。
- **M005/M-L003 GBK**：run.py 打印中文预览禁用 emoji，测试 `PYTHONIOENCODING=utf-8`。
- **半自动红线**：`run.py` 无 `--live` 开关，永远 dry-run/mock，真实发布由人类在浏览器点。

## 6. 交付格式
产出 `docs/evidence/DAY2-D-PACKET.md`，四节：
1. 完成概况
2. 测试结果
3. 文件清单
4. 自查证据（逐条 PASS/FAIL）

**禁止**：run.py 默认 enable 真实平台发布、第 4 节空、夹带积木①②③ 修改。