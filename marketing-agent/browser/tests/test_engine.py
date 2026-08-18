"""浏览器引擎抽象层单元测试。

覆盖 6+ 断言，验证：
    - engine_factory 返回正确实例类型
    - 未知引擎名抛 ValueError
    - UnittestEngine 全部 8 个方法记录 ops
    - BrowserConfig 默认值正确
    - PlaywrightEngine 实例化不抛异常
    - 抽象基类不可实例化

运行::

    python -m pytest browser/tests/test_engine.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

# 让测试可独立运行：把 marketing-agent 目录加到 sys.path。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from browser.engine import (  # noqa: E402
    AbstractBrowserEngine,
    BrowserConfig,
    PlaywrightEngine,
    UnittestEngine,
    engine_factory,
)


class TestEngineFactory(unittest.TestCase):
    """engine_factory 工厂函数测试。"""

    def test_factory_unittest(self):
        """engine_factory("unittest") 返回 UnittestEngine 实例。"""
        engine = engine_factory("unittest")
        self.assertIsInstance(engine, UnittestEngine)
        self.assertIsInstance(engine, AbstractBrowserEngine)

    def test_factory_playwright(self):
        """engine_factory("playwright") 返回 PlaywrightEngine 实例，不抛异常。"""
        engine = engine_factory("playwright")
        self.assertIsInstance(engine, PlaywrightEngine)
        self.assertIsInstance(engine, AbstractBrowserEngine)

    def test_factory_unknown_raises(self):
        """engine_factory("unknown") 抛出 ValueError。"""
        with self.assertRaises(ValueError):
            engine_factory("unknown")


class TestBrowserConfig(unittest.TestCase):
    """BrowserConfig 默认值测试。"""

    def test_default_values(self):
        """BrowserConfig 默认值正确。"""
        cfg = BrowserConfig()
        self.assertTrue(cfg.headless)
        self.assertIsNone(cfg.proxy)
        self.assertIsNone(cfg.user_agent)
        self.assertEqual(cfg.viewport, {"width": 1280, "height": 800})
        self.assertEqual(cfg.locale, "zh-CN")
        self.assertEqual(cfg.timezone_id, "Asia/Shanghai")
        self.assertEqual(cfg.extra_args, {})

    def test_custom_values(self):
        """BrowserConfig 可传入自定义值。"""
        cfg = BrowserConfig(
            headless=False,
            proxy="http://127.0.0.1:8080",
            user_agent="Mozilla/5.0 Custom",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            extra_args={"disable_gpu": True},
        )
        self.assertFalse(cfg.headless)
        self.assertEqual(cfg.proxy, "http://127.0.0.1:8080")
        self.assertEqual(cfg.user_agent, "Mozilla/5.0 Custom")
        self.assertEqual(cfg.viewport, {"width": 1920, "height": 1080})
        self.assertEqual(cfg.locale, "en-US")
        self.assertEqual(cfg.timezone_id, "America/New_York")
        self.assertEqual(cfg.extra_args, {"disable_gpu": True})


class TestUnittestEngine(unittest.TestCase):
    """UnittestEngine 操作日志记录测试。"""

    def setUp(self):
        self.engine = UnittestEngine()

    def test_initialize_records_op(self):
        """initialize 后 ops 含正确记录。"""
        cfg = BrowserConfig()
        self.engine.initialize(cfg)
        self.assertEqual(len(self.engine.ops), 1)
        self.assertEqual(self.engine.ops[0]["op"], "initialize")
        self.assertIs(self.engine.ops[0]["config"], cfg)

    def test_all_8_methods_record_ops(self):
        """全部 8 个方法调用后 ops 记录正确操作名。"""
        cfg = BrowserConfig()
        self.engine.initialize(cfg)
        self.engine.navigate("https://example.com")
        self.engine.fill_form({"#name": "test"})
        self.engine.click("#submit")
        self.engine.screenshot("/tmp/shot.png")
        self.engine.save_storage_state("/tmp/state.json")
        self.engine.load_storage_state("/tmp/state.json")
        self.engine.close()

        self.assertEqual(len(self.engine.ops), 8)

        op_names = [op["op"] for op in self.engine.ops]
        self.assertEqual(op_names, [
            "initialize",
            "navigate",
            "fill_form",
            "click",
            "screenshot",
            "save_storage_state",
            "load_storage_state",
            "close",
        ])

    def test_reset_clears_ops(self):
        """reset() 清空 ops 和 storage_state。"""
        self.engine.initialize(BrowserConfig())
        self.engine.navigate("https://example.com")
        self.assertEqual(len(self.engine.ops), 2)
        self.engine.reset()
        self.assertEqual(len(self.engine.ops), 0)
        self.assertIsNone(self.engine._storage_state)

    def test_storage_state_preserved_across_save_load(self):
        """save_storage_state 初始化 state，load_storage_state 更新 state。"""
        self.assertIsNone(self.engine._storage_state)
        self.engine.save_storage_state("/tmp/state.json")
        self.assertIsNotNone(self.engine._storage_state)
        self.assertEqual(self.engine._storage_state, {"cookies": [], "localStorage": {}})
        self.engine.load_storage_state("/tmp/state2.json")
        self.assertEqual(self.engine._storage_state["source"], "/tmp/state2.json")


class TestPlaywrightEngine(unittest.TestCase):
    """PlaywrightEngine 占位测试（不 import playwright）。"""

    def test_can_instantiate_without_playwright(self):
        """PlaywrightEngine 实例化不依赖 playwright 库。"""
        engine = PlaywrightEngine()
        self.assertIsInstance(engine, PlaywrightEngine)
        self.assertIsNone(engine._browser)
        self.assertIsNone(engine._page)
        self.assertIsNone(engine._playwright)


class TestAbstractBase(unittest.TestCase):
    """抽象基类约束测试。"""

    def test_abstract_cannot_instantiate(self):
        """AbstractBrowserEngine 不可直接实例化。"""
        with self.assertRaises(TypeError):
            AbstractBrowserEngine()  # type: ignore[abstract]  # 测试基类不可实例化


if __name__ == "__main__":
    unittest.main()