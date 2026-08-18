"""多账号管理单元测试。

覆盖 8+ 断言，验证：
    - add() 添加账号成功，重复 id 抛 ValueError
    - get() 正确获取，不存在抛 KeyError
    - remove() 删除成功返回 True
    - list_by_platform() 过滤正确
    - can_publish() 从未发布过返回 True
    - can_publish() 刚发布过返回 False
    - record_publish() 更新时间戳
    - save() + load() 往返一致（重新创建 AccountManager 后账号列表相同）

运行::

    python -m pytest browser/tests/test_account_manager.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# 让测试可独立运行：把 marketing-agent 目录加到 sys.path。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from browser.account_manager import Account, AccountManager  # noqa: E402


def _make_account(account_id="acc_001", platform="xiaohongshu", proxy=None):
    """构造一个测试用 Account。"""
    return Account(
        id=account_id,
        platform=platform,
        nickname=f"nick_{account_id}",
        proxy=proxy,
    )


class TestAccountAdd(unittest.TestCase):
    """AccountManager.add() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_add_succeeds(self):
        """add() 添加账号成功，后续 get() 可取到。"""
        account = _make_account("acc_001")
        self._manager.add(account)
        got = self._manager.get("acc_001")
        self.assertEqual(got.id, "acc_001")
        self.assertEqual(got.platform, "xiaohongshu")

    def test_add_duplicate_id_raises(self):
        """重复 id 添加抛出 ValueError。"""
        self._manager.add(_make_account("acc_001"))
        with self.assertRaises(ValueError):
            self._manager.add(_make_account("acc_001"))

    def test_add_multiple_accounts(self):
        """可添加多个不同 id 的账号。"""
        self._manager.add(_make_account("acc_001", "xiaohongshu"))
        self._manager.add(_make_account("acc_002", "xiaohongshu"))
        self._manager.add(_make_account("acc_003", "douyin"))
        self.assertEqual(len(self._manager._accounts), 3)


class TestAccountGet(unittest.TestCase):
    """AccountManager.get() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_get_existing(self):
        """get() 正确获取已存在的账号。"""
        account = _make_account("acc_001", proxy="http://proxy:8080")
        self._manager.add(account)
        got = self._manager.get("acc_001")
        self.assertEqual(got, account)
        self.assertEqual(got.proxy, "http://proxy:8080")

    def test_get_nonexistent_raises(self):
        """get() 不存在的账号抛出 KeyError。"""
        with self.assertRaises(KeyError):
            self._manager.get("acc_999")


class TestAccountRemove(unittest.TestCase):
    """AccountManager.remove() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_remove_succeeds(self):
        """remove() 删除成功返回 True，账号不再可取。"""
        self._manager.add(_make_account("acc_001"))
        result = self._manager.remove("acc_001")
        self.assertTrue(result)
        with self.assertRaises(KeyError):
            self._manager.get("acc_001")

    def test_remove_nonexistent(self):
        """remove() 不存在的 id 返回 False。"""
        self._manager.add(_make_account("acc_001"))
        result = self._manager.remove("acc_999")
        self.assertFalse(result)
        # 原账号不受影响
        self.assertIsNotNone(self._manager.get("acc_001"))


class TestAccountListByPlatform(unittest.TestCase):
    """AccountManager.list_by_platform() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)
        self._manager.add(_make_account("acc_001", "xiaohongshu"))
        self._manager.add(_make_account("acc_002", "xiaohongshu"))
        self._manager.add(_make_account("acc_003", "douyin"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_filter_by_platform(self):
        """list_by_platform() 按平台正确过滤。"""
        xhs = self._manager.list_by_platform("xiaohongshu")
        self.assertEqual(len(xhs), 2)
        for acc in xhs:
            self.assertEqual(acc.platform, "xiaohongshu")

        dy = self._manager.list_by_platform("douyin")
        self.assertEqual(len(dy), 1)
        self.assertEqual(dy[0].id, "acc_003")

    def test_empty_platform(self):
        """无账号的平台返回空列表。"""
        accounts = self._manager.list_by_platform("empty_platform")
        self.assertEqual(accounts, [])


class TestCanPublish(unittest.TestCase):
    """AccountManager.can_publish() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)
        self._manager.add(_make_account("acc_001"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_never_published_true(self):
        """从未发布过返回 True。"""
        self.assertTrue(self._manager.can_publish("acc_001"))

    def test_recently_published_false(self):
        """刚发布过（< min_interval_hours）返回 False。"""
        self._manager.record_publish("acc_001")
        self.assertFalse(self._manager.can_publish("acc_001"))

    def test_older_than_interval_true(self):
        """超过间隔时间返回 True。"""
        self._manager.record_publish("acc_001")
        # 手动把 last_publish_at 拨回 25 小时前
        acc = self._manager.get("acc_001")
        acc.last_publish_at = time.time() - 25 * 3600
        self.assertTrue(self._manager.can_publish("acc_001"))

    def test_custom_interval(self):
        """自定义 min_interval_hours 生效。"""
        self._manager.record_publish("acc_001")
        # 10 秒前发布，用 0.001 小时（3.6s）间隔 → 应该已过间隔
        acc = self._manager.get("acc_001")
        acc.last_publish_at = time.time() - 10
        self.assertTrue(self._manager.can_publish("acc_001", min_interval_hours=0.001))
        self.assertFalse(self._manager.can_publish("acc_001", min_interval_hours=1))


class TestRecordPublish(unittest.TestCase):
    """AccountManager.record_publish() 测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)
        self._manager.add(_make_account("acc_001"))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_records_timestamp(self):
        """record_publish() 更新 last_publish_at 为当前时间附近。"""
        self.assertIsNone(self._manager.get("acc_001").last_publish_at)
        before = time.time()
        self._manager.record_publish("acc_001")
        after = time.time()
        last = self._manager.get("acc_001").last_publish_at
        self.assertIsNotNone(last)
        self.assertGreaterEqual(last, before)
        self.assertLessEqual(last, after)

    def test_record_publish_nonexistent_raises(self):
        """record_publish() 不存在的 id 抛出 KeyError。"""
        with self.assertRaises(KeyError):
            self._manager.record_publish("acc_999")


class TestPersistence(unittest.TestCase):
    """save() + load() 往返一致性测试。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._data_dir = Path(self._tmpdir.name)
        self._manager = AccountManager(self._data_dir)
        self._manager.add(Account(
            id="acc_001", platform="xiaohongshu", nickname="小红豆",
            proxy="http://proxy1:8080", last_publish_at=123.0,
        ))
        self._manager.add(Account(
            id="acc_002", platform="douyin", nickname="抖音号2",
            proxy=None, last_publish_at=None,
        ))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_save_creates_json(self):
        """save() 在 data_dir 创建 JSON 文件。"""
        self._manager.save()
        files = list(self._data_dir.iterdir())
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].name.endswith(".json"))

    def test_save_load_roundtrip(self):
        """save() + load() 往返后账号列表一致。"""
        self._manager.save()
        new_manager = AccountManager(self._data_dir)
        new_manager.load()
        self.assertEqual(len(new_manager._accounts), 2)
        a1 = new_manager.get("acc_001")
        self.assertEqual(a1.id, "acc_001")
        self.assertEqual(a1.platform, "xiaohongshu")
        self.assertEqual(a1.nickname, "小红豆")
        self.assertEqual(a1.proxy, "http://proxy1:8080")
        self.assertEqual(a1.last_publish_at, 123.0)
        a2 = new_manager.get("acc_002")
        self.assertEqual(a2.platform, "douyin")
        self.assertIsNone(a2.proxy)
        self.assertIsNone(a2.last_publish_at)

    def test_load_empty_file(self):
        """load() 在文件不存在时不应抛异常。"""
        # data_dir 为空，直接 load
        new_manager = AccountManager(self._data_dir)
        new_manager.load()
        self.assertEqual(len(new_manager._accounts), 0)


if __name__ == "__main__":
    unittest.main()