"""Cookie 持久化单元测试。

覆盖 8+ 断言，验证：
    - CookieStore.save() 保存 JSON 到正确路径
    - CookieStore.load() 正确加载已保存的 JSON
    - 不存在的文件 load() 抛出 FileNotFoundError
    - is_valid() 对 1 小时前的 state 返回 True（默认 24h）
    - is_valid() 对 25 小时前的 state 返回 False
    - list_all() 返回所有/指定平台的 state
    - delete() 删除文件并返回 True

运行::

    python -m pytest browser/tests/test_cookie_store.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import json
from pathlib import Path

# 让测试可独立运行：把 marketing-agent 目录加到 sys.path。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from browser.cookie_store import CookieStore, StorageState  # noqa: E402


class TestStorageState(unittest.TestCase):
    """StorageState 数据类基本测试。"""

    def test_dataclass_fields(self):
        """StorageState 有正确的字段。"""
        state = StorageState(
            data={"cookies": [], "localStorage": {}},
            saved_at=1000.0,
            platform="xiaohongshu",
            account_id="acc_001",
        )
        self.assertEqual(state.data, {"cookies": [], "localStorage": {}})
        self.assertEqual(state.saved_at, 1000.0)
        self.assertEqual(state.platform, "xiaohongshu")
        self.assertEqual(state.account_id, "acc_001")


class TestCookieStoreSave(unittest.TestCase):
    """CookieStore.save() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._base_dir = Path(self._tmpdir.name)
        self._store = CookieStore(self._base_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_save_creates_file_at_correct_path(self):
        """save() 在正确路径创建 JSON 文件。"""
        state = StorageState(
            data={"cookies": [{"name": "session", "value": "abc123"}]},
            saved_at=time.time(),
            platform="xiaohongshu",
            account_id="acc_001",
        )
        result_path = self._store.save(state)
        expected_path = self._base_dir / "xiaohongshu_acc_001.json"
        self.assertEqual(result_path, expected_path)
        self.assertTrue(expected_path.exists(), "JSON 文件应被创建")

    def test_save_writes_valid_json(self):
        """save() 写入的 JSON 可被 json.load 正确读取。"""
        state = StorageState(
            data={"cookies": [{"name": "token", "value": "xyz"}]},
            saved_at=time.time(),
            platform="douyin",
            account_id="acc_002",
        )
        self._store.save(state)
        file_path = self._base_dir / "douyin_acc_002.json"
        with open(file_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["data"]["cookies"][0]["name"], "token")
        self.assertEqual(loaded["platform"], "douyin")
        self.assertEqual(loaded["account_id"], "acc_002")


class TestCookieStoreLoad(unittest.TestCase):
    """CookieStore.load() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._base_dir = Path(self._tmpdir.name)
        self._store = CookieStore(self._base_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_load_returns_correct_state(self):
        """load() 正确加载已保存的 JSON。"""
        saved_at = 1000.0
        state = StorageState(
            data={"cookies": [{"name": "session", "value": "abc"}]},
            saved_at=saved_at,
            platform="xiaohongshu",
            account_id="acc_001",
        )
        self._store.save(state)
        loaded = self._store.load("xiaohongshu", "acc_001")
        self.assertEqual(loaded.data, state.data)
        self.assertEqual(loaded.saved_at, saved_at)
        self.assertEqual(loaded.platform, "xiaohongshu")
        self.assertEqual(loaded.account_id, "acc_001")

    def test_load_nonexistent_raises(self):
        """不存在的文件 load() 抛出 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            self._store.load("xiaohongshu", "nonexistent")


class TestCookieStoreIsValid(unittest.TestCase):
    """CookieStore.is_valid() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._base_dir = Path(self._tmpdir.name)
        self._store = CookieStore(self._base_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_is_valid_recent_state(self):
        """1 小时前的 state 应返回 True（默认 24h 有效期）。"""
        saved_at = time.time() - 3600  # 1 小时前
        state = StorageState(
            data={"cookies": []},
            saved_at=saved_at,
            platform="xiaohongshu",
            account_id="acc_001",
        )
        self.assertTrue(self._store.is_valid(state))

    def test_is_valid_old_state(self):
        """25 小时前的 state 应返回 False。"""
        saved_at = time.time() - 25 * 3600  # 25 小时前
        state = StorageState(
            data={"cookies": []},
            saved_at=saved_at,
            platform="xiaohongshu",
            account_id="acc_001",
        )
        self.assertFalse(self._store.is_valid(state))

    def test_is_valid_with_custom_max_age(self):
        """使用自定义 max_age_hours 参数。"""
        saved_at = time.time() - 3 * 3600  # 3 小时前
        state = StorageState(
            data={"cookies": []},
            saved_at=saved_at,
            platform="xiaohongshu",
            account_id="acc_001",
        )
        self.assertTrue(self._store.is_valid(state, max_age_hours=4))
        self.assertFalse(self._store.is_valid(state, max_age_hours=2))


class TestCookieStoreListAll(unittest.TestCase):
    """CookieStore.list_all() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._base_dir = Path(self._tmpdir.name)
        self._store = CookieStore(self._base_dir)
        # 创建多个 state
        self._store.save(StorageState(
            data={}, saved_at=100.0, platform="xiaohongshu", account_id="acc_001",
        ))
        self._store.save(StorageState(
            data={}, saved_at=200.0, platform="xiaohongshu", account_id="acc_002",
        ))
        self._store.save(StorageState(
            data={}, saved_at=300.0, platform="douyin", account_id="acc_003",
        ))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_list_all_returns_all(self):
        """list_all() 返回所有 storageState。"""
        states = self._store.list_all()
        self.assertEqual(len(states), 3)

    def test_list_all_by_platform(self):
        """list_all("xiaohongshu") 只返回 xiaohongshu 的 state。"""
        states = self._store.list_all(platform="xiaohongshu")
        self.assertEqual(len(states), 2)
        for s in states:
            self.assertEqual(s.platform, "xiaohongshu")

    def test_list_all_douyin(self):
        """list_all("douyin") 只返回 douyin 的 state。"""
        states = self._store.list_all(platform="douyin")
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].platform, "douyin")
        self.assertEqual(states[0].account_id, "acc_003")


class TestCookieStoreDelete(unittest.TestCase):
    """CookieStore.delete() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._base_dir = Path(self._tmpdir.name)
        self._store = CookieStore(self._base_dir)
        self._store.save(StorageState(
            data={}, saved_at=100.0, platform="xiaohongshu", account_id="acc_001",
        ))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_delete_removes_file(self):
        """delete() 删除文件并返回 True。"""
        file_path = self._base_dir / "xiaohongshu_acc_001.json"
        self.assertTrue(file_path.exists())
        result = self._store.delete("xiaohongshu", "acc_001")
        self.assertTrue(result)
        self.assertFalse(file_path.exists())

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的文件返回 False。"""
        result = self._store.delete("xiaohongshu", "nonexistent")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()