"""人工确认闸单元测试。

测试策略：
    - 模拟 input_fn 注入各种输入，验证 GateDecision
    - 验证 generate_preview 格式
    - 验证 is_auto_publish_disabled 始终返回 True
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import List

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_AGENT_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from publish.human_gate import HumanGate, GateDecision  # noqa: E402


def _make_input_fn(answers: List[str]):
    """创建模拟 input_fn，依次返回给定答案列表。"""
    idx = [0]

    def fn(prompt: str) -> str:
        val = answers[idx[0] % len(answers)]
        idx[0] += 1
        return val

    return fn


class TestHumanGatePreview(unittest.TestCase):
    """HumanGate.generate_preview() 验证。"""

    def test_preview_contains_platform_and_title(self):
        """预览文本包含平台、标题、标签信息"""
        gate = HumanGate()
        summary = {
            "platform": "xiaohongshu",
            "title": "测试标题",
            "body_summary": "这是正文摘要...",
            "tags": ["教育", "学习"],
            "image_count": 3,
            "schedule_time": None,
            "location": "北京",
        }
        preview = gate.generate_preview("xiaohongshu", summary)
        self.assertIn("xiaohongshu", preview)
        self.assertIn("测试标题", preview)
        self.assertIn("教育", preview)
        self.assertIn("学习", preview)
        self.assertIn("图片数量: 3", preview)
        self.assertIn("立即", preview)

    def test_preview_with_douyin_fields(self):
        """抖音预览包含视频字段"""
        gate = HumanGate()
        summary = {
            "platform": "douyin",
            "title": "视频标题",
            "video_path": "video.mp4",
            "topics": ["教育"],
            "schedule_time": "2026-08-20T10:00:00",
            "location": "上海",
        }
        preview = gate.generate_preview("douyin", summary)
        self.assertIn("douyin", preview)
        self.assertIn("视频标题", preview)
        self.assertIn("video.mp4", preview)
        self.assertIn("2026-08-20T10:00:00", preview)


class TestHumanGateConfirm(unittest.TestCase):
    """HumanGate.request_confirm() 决策验证。"""

    def test_yes_returns_confirm(self):
        """输入 "Y" 返回 CONFIRM"""
        gate = HumanGate(input_fn=_make_input_fn(["Y"]))
        preview = "预览内容"
        result = gate.request_confirm(preview)
        self.assertEqual(result.decision, GateDecision.CONFIRM)

    def test_yes_lowercase_returns_confirm(self):
        """输入 "y" 返回 CONFIRM"""
        gate = HumanGate(input_fn=_make_input_fn(["y"]))
        result = gate.request_confirm("预览")
        self.assertEqual(result.decision, GateDecision.CONFIRM)

    def test_yes_full_word_returns_confirm(self):
        """输入 "yes" 返回 CONFIRM"""
        gate = HumanGate(input_fn=_make_input_fn(["yes"]))
        result = gate.request_confirm("预览")
        self.assertEqual(result.decision, GateDecision.CONFIRM)

    def test_no_returns_abort(self):
        """输入 "N" 返回 ABORT"""
        gate = HumanGate(input_fn=_make_input_fn(["N"]))
        result = gate.request_confirm("预览")
        self.assertEqual(result.decision, GateDecision.ABORT)

    def test_no_lowercase_returns_abort(self):
        """输入 "n" 返回 ABORT"""
        gate = HumanGate(input_fn=_make_input_fn(["n"]))
        result = gate.request_confirm("预览")
        self.assertEqual(result.decision, GateDecision.ABORT)

    def test_edit_returns_edit(self):
        """输入 "E" 返回 EDIT"""
        gate = HumanGate(input_fn=_make_input_fn(["E"]))
        result = gate.request_confirm("预览")
        self.assertEqual(result.decision, GateDecision.EDIT)

    def test_invalid_then_valid_retries(self):
        """无效输入后重试，最终有效输入返回正确决策"""
        gate = HumanGate(input_fn=_make_input_fn(["x", "?", "Y"]))
        result = gate.request_confirm("预览")
        self.assertEqual(result.decision, GateDecision.CONFIRM)


class TestHumanGateStatic(unittest.TestCase):
    """HumanGate 静态方法验证。"""

    def test_is_auto_publish_disabled_returns_true(self):
        """is_auto_publish_disabled() 始终返回 True"""
        self.assertTrue(HumanGate.is_auto_publish_disabled())
        self.assertTrue(HumanGate().is_auto_publish_disabled())


if __name__ == "__main__":
    unittest.main(verbosity=2)