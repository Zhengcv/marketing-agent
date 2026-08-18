"""多账号管理积木。

按账号隔离存储，支持增删查 + 平台绑定 + 代理绑定 + 发布间隔控制。

用法::

    manager = AccountManager(Path("./accounts"))
    manager.load()
    manager.add(Account(
        id="acc_001", platform="xiaohongshu", nickname="小红豆",
        proxy="http://15.0.0.1:8080",
    ))
    if manager.can_publish("acc_001"):
        ...  # 发布前检查通过
        manager.record_publish("acc_001")
    manager.save()
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Any, Dict


@dataclass
class Account:
    """单个运营账号。

    Attributes:
        id: 唯一标识。
        platform: 平台名，如 "xiaohongshu"、"douyin"。
        nickname: 平台昵称。
        proxy: 绑定的住宅代理地址（可选）。
        storage_state_path: Cookie 存储路径（可选）。
        last_publish_at: 上次发布时间戳（可选）。
        created_at: 创建时间戳。
    """
    id: str
    platform: str
    nickname: str
    proxy: Optional[str] = None
    storage_state_path: Optional[Path] = None
    last_publish_at: Optional[float] = None
    created_at: float = field(default_factory=lambda: time.time())


class AccountManager:
    """账号集合管理。

    Attributes:
        _data_dir: 持久化 JSON 文件所在目录。
        _accounts: 内存中的账号列表。
    """

    def __init__(self, data_dir: Path):
        """初始化 AccountManager。

        Args:
            data_dir: 持久化 JSON 文件所在目录。
        """
        self._data_dir = data_dir
        self._accounts: List[Account] = []

    # ------------------------------------------------------------------
    # 增删查
    # ------------------------------------------------------------------

    def add(self, account: Account) -> None:
        """添加账号。

        Args:
            account: 要添加的 Account 对象。

        Raises:
            ValueError: id 已存在时抛出。
        """
        for existing in self._accounts:
            if existing.id == account.id:
                raise ValueError(f"Account id already exists: {account.id}")
        self._accounts.append(account)

    def remove(self, account_id: str) -> bool:
        """删除账号。

        Args:
            account_id: 账号唯一标识。

        Returns:
            True 表示成功删除，False 表示 id 不存在。
        """
        for idx, account in enumerate(self._accounts):
            if account.id == account_id:
                del self._accounts[idx]
                return True
        return False

    def get(self, account_id: str) -> Account:
        """获取账号。

        Args:
            account_id: 账号唯一标识。

        Returns:
            匹配的 Account 对象。

        Raises:
            KeyError: 不存在该 id 时抛出。
        """
        for account in self._accounts:
            if account.id == account_id:
                return account
        raise KeyError(f"Account not found: {account_id}")

    def list_by_platform(self, platform: str) -> List[Account]:
        """列出指定平台的所有账号。

        Args:
            platform: 平台名。

        Returns:
            该平台下的账号列表。
        """
        return [
            account
            for account in self._accounts
            if account.platform == platform
        ]

    # ------------------------------------------------------------------
    # 发布间隔控制
    # ------------------------------------------------------------------

    def can_publish(self, account_id: str, min_interval_hours: int = 24) -> bool:
        """检查账号是否满足发布间隔。

        Args:
            account_id: 账号唯一标识。
            min_interval_hours: 最小发布间隔（小时），默认 24 小时。

        Returns:
            True 表示可以发布，False 表示距离上次发布太近。

        Raises:
            KeyError: 不存在该 id 时抛出。
        """
        account = self.get(account_id)
        if account.last_publish_at is None:
            # 从未发布过
            return True
        interval_seconds = min_interval_hours * 3600
        return (time.time() - account.last_publish_at) >= interval_seconds

    def record_publish(self, account_id: str) -> None:
        """记录一次发布时间。

        Args:
            account_id: 账号唯一标识。

        Raises:
            KeyError: 不存在该 id 时抛出。
        """
        account = self.get(account_id)
        account.last_publish_at = time.time()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _accounts_file(self) -> Path:
        """accounts JSON 文件路径。"""
        return self._data_dir / "accounts.json"

    def _account_to_dict(self, account: Account) -> Dict[str, Any]:
        """把 Account 转成 JSON 字典。"""
        data: Dict[str, Any] = {
            "id": account.id,
            "platform": account.platform,
            "nickname": account.nickname,
            "proxy": account.proxy,
            "storage_state_path": (
                str(account.storage_state_path)
                if account.storage_state_path is not None
                else None
            ),
            "last_publish_at": account.last_publish_at,
            "created_at": account.created_at,
        }
        return data

    def _dict_to_account(self, data: Dict[str, Any]) -> Account:
        """把 JSON 字典还原成 Account。"""
        storage_path = data.get("storage_state_path")
        return Account(
            id=data["id"],
            platform=data["platform"],
            nickname=data["nickname"],
            proxy=data.get("proxy"),
            storage_state_path=(
                Path(storage_path) if storage_path is not None else None
            ),
            last_publish_at=data.get("last_publish_at"),
            created_at=data.get("created_at", time.time()),
        )

    def save(self) -> None:
        """将账号列表持久化到 JSON 文件。"""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        serialized = [self._account_to_dict(a) for a in self._accounts]
        with open(self._accounts_file(), "w", encoding="utf-8") as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """从 JSON 文件加载账号列表。

        文件不存在时静默清空列表（视同无账号）。
        """
        self._accounts = []
        accounts_file = self._accounts_file()
        if not accounts_file.exists():
            return
        with open(accounts_file, "r", encoding="utf-8") as f:
            serialized = json.load(f)
        self._accounts = [self._dict_to_account(item) for item in serialized]