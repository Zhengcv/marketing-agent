"""小红书发布器单元测试。

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
from publish.platforms.xiaohongshu import XhsPublisher, XhsPost  # noqa: E402


class TestXhsValidate(unittest.TestCase):
    """XhsPublisher.validate() 校验逻辑验证。"""

    def test_empty_title_returns_error(self):
        """空标题返回 ["标题不能为空"]"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(title="", body="正文内容", images=[Path("a.jpg")])
        errors = pub.validate(post)
        self.assertIn("标题不能为空", errors)

    def test_title_too_long_returns_error(self):
        """标题 >20 字返回 ["标题不能超过20字"]"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(title="a" * 21, body="正文", images=[Path("a.jpg")])
        errors = pub.validate(post)
        self.assertIn("标题不能超过20字", errors)

    def test_too_many_tags_returns_error(self):
        """6 个标签返回 ["标签不能超过5个"]"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(
            title="标题",
            body="正文",
            tags=["t1", "t2", "t3", "t4", "t5", "t6"],
            images=[Path("a.jpg")],
        )
        errors = pub.validate(post)
        self.assertIn("标签不能超过5个", errors)

    def test_empty_body_returns_error(self):
        """空正文返回 ["正文不能为空"]"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(title="标题", body="", images=[Path("a.jpg")])
        errors = pub.validate(post)
        self.assertIn("正文不能为空", errors)

    def test_valid_post_returns_empty(self):
        """合法内容返回空列表"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(
            title="标题",
            body="正文内容",
            tags=["tag1", "tag2"],
            images=[Path("a.jpg"), Path("b.png")],
        )
        errors = pub.validate(post)
        self.assertEqual(errors, [])

    def test_no_images_returns_error(self):
        """无图片返回错误"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(title="标题", body="正文", images=[])
        errors = pub.validate(post)
        self.assertIn("至少需要1张图片", errors)

    def test_too_many_images_returns_error(self):
        """超过9张图片返回错误"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(
            title="标题",
            body="正文",
            images=[Path(f"{i}.jpg") for i in range(10)],
        )
        errors = pub.validate(post)
        self.assertIn("图片不能超过9张", errors)


class TestXhsFillForm(unittest.TestCase):
    """XhsPublisher.fill_form() 操作顺序验证。"""

    def test_fill_form_records_ops(self):
        """fill_form 后引擎 ops 包含 navigate + fill_form 操作"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(
            title="测试标题",
            body="测试正文内容",
            tags=["教育", "学习"],
            images=[Path("img1.jpg"), Path("img2.jpg")],
        )
        result = pub.fill_form(post)
        op_names = [op["op"] for op in engine.ops]
        self.assertIn("navigate", op_names)
        self.assertIn("fill_form", op_names)
        self.assertEqual(result["platform"], "xiaohongshu")
        self.assertEqual(result["title"], "测试标题")
        self.assertEqual(result["image_count"], 2)

    def test_fill_form_validates_first(self):
        """fill_form 在非法内容时抛出 ValueError，不执行引擎操作"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(title="", body="", images=[])
        with self.assertRaises(ValueError):
            pub.fill_form(post)
        self.assertEqual(engine.ops, [])


class TestXhsPublish(unittest.TestCase):
    """XhsPublisher.publish() 操作验证。"""

    def test_publish_after_fill_form_clicks(self):
        """fill_form 后调用 publish，引擎 ops 包含 click"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        post = XhsPost(
            title="标题",
            body="正文",
            images=[Path("a.jpg")],
        )
        pub.fill_form(post)
        pub.publish()
        click_ops = [op for op in engine.ops if op["op"] == "click"]
        self.assertEqual(len(click_ops), 1)
        self.assertEqual(click_ops[0]["selector"], "#publish-btn")

    def test_publish_without_fill_form_raises(self):
        """未调用 fill_form 就 publish 抛出 RuntimeError"""
        engine = UnittestEngine()
        pub = XhsPublisher(engine)
        with self.assertRaises(RuntimeError):
            pub.publish()


if __name__ == "__main__":
    unittest.main(verbosity=2)