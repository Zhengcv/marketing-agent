# Lane B · browser/cookie_store.py + browser/account_manager.py + requirements.txt · 积木⑤ 反检测底座（Cookie+账号管理）

**分派对象**: exec-luna
**积木**: ⑤ browser（反检测底座）
**轮次**: 第 1 轮（与 Lane A 并行，无依赖）
**产出**: `marketing-agent/browser/cookie_store.py`, `marketing-agent/browser/account_manager.py`, `marketing-agent/requirements.txt`, 测试

---

## 0. 任务是什么

1. **Cookie 持久化**：保存/加载/验证 storageState JSON（复用登录态，永不重放登录）
2. **多账号管理**：按账号隔离存储，支持增删查
3. **requirements.txt**：统一项目依赖声明（当前项目无此文件）

## 1. 文件清单

| 文件 | 说明 |
|------|------|
| `marketing-agent/browser/cookie_store.py` | Cookie 持久化（storageState 读写 + 有效性校验） |
| `marketing-agent/browser/account_manager.py` | 多账号管理（增删查 + 平台绑定 + 代理绑定） |
| `marketing-agent/browser/tests/test_cookie_store.py` | Cookie 存储测试 |
| `marketing-agent/browser/tests/test_account_manager.py` | 账号管理测试 |
| `marketing-agent/requirements.txt` | 项目 Python 依赖声明 |

## 2. 接口契约（冻结）

### 2.1 cookie_store.py

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
import json
import time

@dataclass
class StorageState:
    data: Dict[str, Any]  # 完整的 storageState JSON（cookies + localStorage）
    saved_at: float  # 保存时间戳
    platform: str  # "xiaohongshu" | "douyin"
    account_id: str  # 账号标识

class CookieStore:
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def save(self, state: StorageState) -> Path:
        """保存 storageState 到磁盘。文件命名: {platform}_{account_id}.json。
        返回保存的文件路径。"""

    def load(self, platform: str, account_id: str) -> StorageState:
        """从磁盘加载 storageState。文件不存在抛出 FileNotFoundError。"""

    def is_valid(self, state: StorageState, max_age_hours: int = 24) -> bool:
        """检查 storageState 是否有效（未过期）。"""

    def list_all(self, platform: Optional[str] = None) -> list[StorageState]:
        """列出所有/指定平台的 storageState。"""

    def delete(self, platform: str, account_id: str) -> bool:
        """删除指定账号的 storageState。返回是否成功删除。"""
```

### 2.2 account_manager.py

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

@dataclass
class Account:
    id: str  # 唯一标识
    platform: str  # "xiaohongshu" | "douyin"
    nickname: str  # 平台昵称
    proxy: Optional[str] = None  # 绑定的住宅代理地址
    storage_state_path: Optional[Path] = None  # Cookie 存储路径
    last_publish_at: Optional[float] = None  # 上次发布时间戳
    created_at: float = field(default_factory=lambda: __import__("time").time())

class AccountManager:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._accounts: List[Account] = []

    def add(self, account: Account) -> None:
        """添加账号。id 重复抛出 ValueError。"""

    def remove(self, account_id: str) -> bool:
        """删除账号。"""

    def get(self, account_id: str) -> Account:
        """获取账号。不存在抛出 KeyError。"""

    def list_by_platform(self, platform: str) -> List[Account]:
        """列出指定平台的所有账号。"""

    def can_publish(self, account_id: str, min_interval_hours: int = 24) -> bool:
        """检查账号是否满足发布间隔（默认 24h）。"""

    def record_publish(self, account_id: str) -> None:
        """记录一次发布时间。"""

    def save(self) -> None:
        """将账号列表持久化到 JSON 文件。"""

    def load(self) -> None:
        """从 JSON 文件加载账号列表。"""
```

## 3. 验收标准

### cookie_store.py
- [ ] `CookieStore.save()` 保存 JSON 文件到正确路径
- [ ] `CookieStore.load()` 正确加载已保存的 JSON
- [ ] 不存在的文件 `load()` 抛出 FileNotFoundError
- [ ] `is_valid()` 对 1 小时前的 state 返回 True（默认 24h）
- [ ] `is_valid()` 对 25 小时前的 state 返回 False
- [ ] `list_all()` 返回所有/指定平台的 state
- [ ] `delete()` 删除文件并返回 True

### account_manager.py
- [ ] `add()` 添加账号成功，重复 id 抛 ValueError
- [ ] `get()` 正确获取，不存在抛 KeyError
- [ ] `remove()` 删除成功返回 True
- [ ] `list_by_platform()` 过滤正确
- [ ] `can_publish()` 从未发布过返回 True
- [ ] `can_publish()` 刚发布过返回 False
- [ ] `record_publish()` 更新时间戳
- [ ] `save()` + `load()` 往返一致（重新创建 AccountManager 后账号列表相同）

### requirements.txt
- [ ] 包含 `requests` 依赖（积木① 已用，但未声明）
- [ ] 包含 `pytest`（测试框架）
- [ ] 每行一个包，格式 `<package_name>`（暂不指定版本号，当前环境无版控）

## 4. 测试要求

- 至少 16 个测试（cookie_store: 8 + account_manager: 8）
- 使用 tempfile 创建临时目录，测试后清理
- 测试独立运行：`python -m pytest browser/tests/ -v`
- 全绿，无假绿

## 5. ⚠️ 历史同类坑（必读）

1. **M001/M-L002 路径硬编码**：`CookieStore.__init__` 接收 `base_dir: Path` 参数，不内部写死路径。`AccountManager` 同理。禁止 `Path("docs/...")` 硬编码。
2. **M002/M-L001 仓库根**：commit 前 `git -C D:/llm/marketing-agent rev-parse --show-toplevel`。`requirements.txt` 放在 `marketing-agent/` 目录下（仓库根 `D:/llm/marketing-agent/`），别放错层级。
3. **M005/M-L003 Windows GBK**：测试文件不打印 emoji。用 `PYTHONIOENCODING=utf-8` 跑测试。
4. **M003/M-L005 .gitignore**：如果新增 `__pycache__/` 或 `*.pyc` 到 .gitignore，改完逐行 `cat` 看，`git check-ignore` 验证。注意 .gitignore 在 `marketing-agent/` 子目录（嵌套仓库根下一层），改仓库根的 .gitignore 还是代码目录的 .gitignore，要分清楚。

## 6. 交付格式

产出 `docs/evidence/DAY2-B-PACKET.md`，四节：
1. 完成概况
2. 测试结果
3. 文件清单
4. 自查证据（逐条验收标准 PASS/FAIL）

**禁止**：第 4 节为空、夹带积木①②③ 的文件修改、跳过 `browser/tests/__init__.py` 创建。