"""抖音发布器单元测试。

测试策略：
    - 使用 Lane A 的 UnittestEngine 验证表单字段结构与引擎操作顺序
    - 不依赖真实浏览器，完全离线运行
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from browser.engine import UnittestEngine  # noqa: E402
from publish.platforms.douyin import DyPublisher, DyPost  # noqa: E402


class TestDyValidate(unittest.TestCase):
    """DyPublisher.validate() 校验逻辑验证。"""

    def test_empty_title_returns_error(self):
        """空标题返回 ["标题不能为空"]"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(title="", video_path=Path("video.mp4"))
        errors = pub.validate(post)
        self.assertIn("标题不能为空", errors)

    def test_title_too_long_returns_error(self):
        """标题 >55 字返回违规"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(title="a" * 56, video_path=Path("video.mp4"))
        errors = pub.validate(post)
        self.assertIn("标题不能超过55字", errors)

    def test_no_video_returns_error(self):
        """video_path 为 None 时返回违规"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(title="标题", video_path=None)  # type: ignore
        errors = pub.validate(post)
        self.assertIn("视频文件路径不能为空", errors)

    def test_too_many_topics_returns_error(self):
        """超过5个话题返回违规"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(
            title="标题",
            video_path=Path("video.mp4"),
            topics=["t1", "t2", "t3", "t4", "t5", "t6"],
        )
        errors = pub.validate(post)
        self.assertIn("话题不能超过5个", errors)

    def test_valid_post_returns_empty(self):
        """合法内容返回空列表"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(
            title="视频描述",
            video_path=Path("video.mp4"),
            topics=["教育", "学习"],
            cover_path=Path("cover.jpg"),
        )
        errors = pub.validate(post)
        self.assertEqual(errors, [])


class TestDyFillForm(unittest.TestCase):
    """DyPublisher.fill_form() 操作顺序验证。"""

    def test_fill_form_records_ops(self):
        """fill_form 后引擎 ops 包含 navigate + fill_form 操作"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(
            title="测试视频描述",
            video_path=Path("video.mp4"),
            topics=["教育", "学习"],
        )
        result = pub.fill_form(post)
        op_names = [op["op"] for op in engine.ops]
        self.assertIn("navigate", op_names)
        self.assertIn("fill_form", op_names)
        self.assertEqual(result["platform"], "douyin")
        self.assertEqual(result["title"], "测试视频描述")
        self.assertEqual(result["video_path"], "video.mp4")

    def test_fill_form_validates_first(self):
        """fill_form 在非法内容时抛出 ValueError，不执行引擎操作"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(title="", video_path=Path("video.mp4"))
        with self.assertRaises(ValueError):
            pub.fill_form(post)
        self.assertEqual(engine.ops, [])


class TestDyPublish(unittest.TestCase):
    """DyPublisher.publish() 操作验证。"""

    def test_publish_after_fill_form_clicks(self):
        """fill_form 后调用 publish，引擎 ops 包含 click"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        post = DyPost(title="标题", video_path=Path("video.mp4"))
        pub.fill_form(post)
        pub.publish()
        click_ops = [op for op in engine.ops if op["op"] == "click"]
        self.assertEqual(len(click_ops), 1)
        self.assertEqual(click_ops[0]["selector"], "#publish-btn")

    def test_publish_without_fill_form_raises(self):
        """未调用 fill_form 就 publish 抛出 RuntimeError"""
        engine = UnittestEngine()
        pub = DyPublisher(engine)
        with self.assertRaises(RuntimeError):
            pub.publish()


if __name__ == "__main__":
    unittest.main(verbosity=2)