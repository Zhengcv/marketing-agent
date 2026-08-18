"""Cookie 持久化积木。

保存/加载/验证 storageState JSON（复用登录态，永不重放登录）。

用法::

    store = CookieStore(Path("./states"))
    state = StorageState(
        data={"cookies": [...], "localStorage": [...]},
        saved_at=time.time(),
        platform="xiaohongshu",
        account_id="acc_001",
    )
    store.save(state)
    loaded = store.load("xiaohongshu", "acc_001")
    if store.is_valid(loaded):
        # 复用登录态
        ...
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List


@dataclass
class StorageState:
    """完整的 storageState 数据。

    Attributes:
        data: 完整的 storageState JSON（cookies + localStorage）。
        saved_at: 保存时间戳（秒）。
        platform: 平台名，如 "xiaohongshu"、"douyin"。
        account_id: 账号标识。
    """
    data: Dict[str, Any]
    saved_at: float
    platform: str
    account_id: str


class CookieStore:
    """Cookie 持久化存储管理层。

    Attributes:
        _base_dir: 存储 JSON 文件的根目录。
    """

    def __init__(self, base_dir: Path):
        """初始化 CookieStore。

        Args:
            base_dir: 存储 JSON 文件的根目录。目录不存在时会自动创建。
        """
        self._base_dir = base_dir

    def _file_path(self, platform: str, account_id: str) -> Path:
        """构造文件路径。"""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        return self._base_dir / f"{platform}_{account_id}.json"

    def save(self, state: StorageState) -> Path:
        """保存 storageState 到磁盘。

        Args:
            state: 要保存的 StorageState 对象。

        Returns:
            保存的文件路径。
        """
        file_path = self._file_path(state.platform, state.account_id)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "data": state.data,
            "saved_at": state.saved_at,
            "platform": state.platform,
            "account_id": state.account_id,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return file_path

    def load(self, platform: str, account_id: str) -> StorageState:
        """从磁盘加载 storageState。

        Args:
            platform: 平台名。
            account_id: 账号标识。

        Returns:
            加载的 StorageState 对象。

        Raises:
            FileNotFoundError: 文件不存在时抛出。
        """
        file_path = self._file_path(platform, account_id)
        if not file_path.exists():
            raise FileNotFoundError(
                f"StorageState file not found: {file_path}"
            )
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StorageState(
            data=data["data"],
            saved_at=data["saved_at"],
            platform=data["platform"],
            account_id=data["account_id"],
        )

    def is_valid(self, state: StorageState, max_age_hours: int = 24) -> bool:
        """检查 storageState 是否有效（未过期）。

        Args:
            state: 要检查的 StorageState。
            max_age_hours: 最大有效期（小时），默认 24 小时。

        Returns:
            True 表示 state 仍然有效，False 表示已过期。
        """
        max_age_seconds = max_age_hours * 3600
        return (time.time() - state.saved_at) < max_age_seconds

    def list_all(self, platform: Optional[str] = None) -> List[StorageState]:
        """列出所有/指定平台的 storageState。

        Args:
            platform: 可选，指定平台名。为 None 时列出所有平台。

        Returns:
            StorageState 列表。
        """
        if not self._base_dir.exists():
            return []
        results: List[StorageState] = []
        for file_path in self._base_dir.iterdir():
            if not file_path.is_file() or not file_path.name.endswith(".json"):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if platform is not None and data.get("platform") != platform:
                continue
            results.append(StorageState(
                data=data["data"],
                saved_at=data["saved_at"],
                platform=data["platform"],
                account_id=data["account_id"],
            ))
        return results

    def delete(self, platform: str, account_id: str) -> bool:
        """删除指定账号的 storageState。

        Args:
            platform: 平台名。
            account_id: 账号标识。

        Returns:
            True 表示成功删除，False 表示文件不存在。
        """
        file_path = self._file_path(platform, account_id)
        if not file_path.exists():
            return False
        file_path.unlink()
        return True