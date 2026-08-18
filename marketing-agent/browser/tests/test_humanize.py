"""真人行为模拟器单元测试。

覆盖 6+ 断言，验证：
    - generate_bezier_path 返回正确数量的坐标，首尾精确匹配
    - 贝塞尔路径弯曲（非直线段）
    - human_type 返回 list of dict，每键有 char/delay_ms/corrected
    - human_type error_rate=0 无 corrected 键，error_rate=1.0 全 corrected
    - random_pause 返回值在 [min_ms, max_ms] 范围内
    - mouse_jitter 偏移在 [-amplitude, amplitude] 范围内

运行::

    python -m pytest browser/tests/test_humanize.py -v
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

from browser.humanize import (  # noqa: E402
    generate_bezier_path,
    human_type,
    mouse_jitter,
    random_pause,
)


class TestBezierPath(unittest.TestCase):
    """贝塞尔曲线鼠标路径测试。"""

    def test_returns_correct_number_of_steps(self):
        """generate_bezier_path((0,0), (100,100), 30) 返回 30 个坐标。"""
        path = generate_bezier_path((0, 0), (100, 100), steps=30)
        self.assertEqual(len(path), 30)

    def test_first_and_last_points_match(self):
        """首尾坐标精确匹配输入。"""
        start = (10, 20)
        end = (350, 480)
        path = generate_bezier_path(start, end, steps=20)
        # 首尾因为 jitter 不施加，精确匹配
        self.assertAlmostEqual(path[0][0], start[0], places=5)
        self.assertAlmostEqual(path[0][1], start[1], places=5)
        self.assertAlmostEqual(path[-1][0], end[0], places=5)
        self.assertAlmostEqual(path[-1][1], end[1], places=5)

    def test_path_is_not_straight_line(self):
        """贝塞尔路径弯曲，非直线段（控制点随机偏移）。"""
        # 多次运行取足够长的路径，期望至少一个中间点偏离直线
        start = (0, 0)
        end = (200, 0)
        # 直线路径恒为 (x, 0)；中间点若有 y != 0 即弯曲
        path = generate_bezier_path(start, end, steps=50, jitter=0)
        mid_y_values = [pt[1] for pt in path[1:-1]]
        # 至少有一个中间点 y 轴偏离 0
        has_curve = any(abs(y) > 1.0 for y in mid_y_values)
        self.assertTrue(has_curve, "贝塞尔路径应是弯曲的，但所有中间点 y=0")

    def test_minimum_steps(self):
        """steps < 2 时自动保底为 2。"""
        path = generate_bezier_path((0, 0), (10, 10), steps=1)
        self.assertEqual(len(path), 2)

    def test_jitter_affects_inner_points(self):
        """jitter 对内点有影响，首尾不受影响。"""
        # 高 jitter 时中间点应有较大散度
        path1 = generate_bezier_path((0, 0), (100, 100), steps=30, jitter=0)
        path2 = generate_bezier_path((0, 0), (100, 100), steps=30, jitter=50)
        # 首尾精确相等
        self.assertEqual(path1[0], path2[0])
        self.assertEqual(path1[-1], path2[-1])
        # 中间点不完全相同（概率极高，除非随机种子极巧合）
        mid_diffs = []
        for i in range(1, len(path1) - 1):
            d = abs(path1[i][0] - path2[i][0]) + abs(path1[i][1] - path2[i][1])
            mid_diffs.append(d)
        # 至少有一个点差异 > 0.1
        self.assertTrue(any(d > 0.1 for d in mid_diffs), "jitter 应影响中间点")


class TestHumanType(unittest.TestCase):
    """真人键盘输入测试。"""

    def test_returns_list_of_dicts_with_required_keys(self):
        """human_type 返回 list of dict，每键有 char/delay_ms/corrected。"""
        result = human_type("hello", wpm=60, error_rate=0)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for entry in result:
            self.assertIn("char", entry)
            self.assertIn("delay_ms", entry)
            self.assertIn("corrected", entry)
            self.assertIsInstance(entry["char"], str)
            self.assertIsInstance(entry["delay_ms"], (int, float))
            self.assertIsInstance(entry["corrected"], bool)

    def test_zero_error_rate_no_corrected_keys(self):
        """error_rate=0 时所有键 corrected=False。"""
        result = human_type("hello", wpm=60, error_rate=0)
        for entry in result:
            self.assertFalse(entry["corrected"], f"error_rate=0 不应有 corrected: {entry}")

    def test_high_error_rate_has_corrected_keys(self):
        """error_rate=1.0 时每键都标记 corrected=True（概率边界检验）。"""
        # 用长文本确保统计稳定
        result = human_type("a" * 50, wpm=60, error_rate=1.0)
        # 每个字符应该产生：错误字符 → 退格 → 正确字符（corrected=True）
        # 所以 corrected=True 的条目数应该 == 文本长度
        corrected_count = sum(1 for e in result if e["corrected"])
        self.assertEqual(corrected_count, 50, "error_rate=1.0 应每键都有 corrected=True")

    def test_each_char_has_delay_ms(self):
        """每键 delay_ms 为正数。"""
        result = human_type("test", wpm=60, error_rate=0)
        for entry in result:
            self.assertGreater(entry["delay_ms"], 0)

    def test_output_length_with_errors(self):
        """有错误时输出长度 > 输入长度（含错误字符 + 退格）。"""
        result = human_type("ab", wpm=60, error_rate=1.0)
        # "ab" → 每键: 错误 + 退格 + 正确 = 3 条/键 × 2 = 6 条
        self.assertGreater(len(result), 2)


class TestRandomPause(unittest.TestCase):
    """随机停留测试。"""

    def test_within_range(self):
        """random_pause(200, 3000) 返回 float 在 [200, 3000] 范围内。"""
        for _ in range(100):
            pause = random_pause(200, 3000)
            self.assertGreaterEqual(pause, 200, f"停留时间 {pause} < 200")
            self.assertLessEqual(pause, 3000, f"停留时间 {pause} > 3000")

    def test_min_equals_max(self):
        """min_ms == max_ms 时返回 min_ms。"""
        pause = random_pause(500, 500)
        self.assertEqual(pause, 500.0)

    def test_returns_float(self):
        """保证返回 float 类型。"""
        pause = random_pause(200, 3000)
        self.assertIsInstance(pause, float)


class TestMouseJitter(unittest.TestCase):
    """鼠标抖动测试。"""

    def test_offset_within_amplitude(self):
        """mouse_jitter((100, 100), 2) 偏移在 [-2, 2] 范围内。"""
        for _ in range(100):
            x, y = mouse_jitter((100, 100), 2)
            self.assertLessEqual(abs(x - 100), 2, f"x 偏移超出: {x - 100}")
            self.assertLessEqual(abs(y - 100), 2, f"y 偏移超出: {y - 100}")

    def test_zero_amplitude_no_offset(self):
        """amplitude=0 时坐标不变。"""
        for _ in range(50):
            x, y = mouse_jitter((50, 80), 0)
            self.assertEqual(x, 50)
            self.assertEqual(y, 80)

    def test_returns_tuple_of_ints(self):
        """返回 (int, int) 元组。"""
        result = mouse_jitter((100, 100), 3)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], int)
        self.assertIsInstance(result[1], int)


if __name__ == "__main__":
    unittest.main()