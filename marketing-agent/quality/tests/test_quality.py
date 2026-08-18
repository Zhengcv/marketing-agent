"""质量门 TDD 测试：先锁定公开行为，再实现启发式规则。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

# 允许从 ``python quality/tests/`` 直接执行。
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quality.anti_ai import detect_ai_traces
from quality.expert_panel import review_content
from quality.seven_sweeps import run_seven_sweeps


GOOD = """找家教最怕什么？花了钱，孩子还不想学。
我帮一个杭州妈妈对接老师时，先让她核对 L1 实名、L2 学历和 L3 教资，再约试讲。
信息费由老师单边付，家长只付课时费；试讲后可以问孩子还想不想继续。
你还在担心什么？评论区聊聊，私信“老师名单”领取已认证老师清单。"""

AI_TEXT = """在当今社会，教育服务非常优质专业，能够高效便捷地为家长提供一站式支持。
值得注意的是，我们将进行全方位服务。总而言之，选择我们即可省时间。
1. 了解需求
2. 匹配老师
3. 预约沟通
4. 试讲确认
5. 开始服务
"""


class QualityGateTests(unittest.TestCase):
    def test_ai_filler_phrases_are_detected(self) -> None:
        traces = detect_ai_traces(AI_TEXT)
        quotes = {trace.quote for trace in traces}
        self.assertIn("在当今社会", quotes)
        self.assertIn("总而言之", quotes)
        self.assertGreaterEqual(len(traces), 8)

    def test_weak_and_hollow_words_are_detected(self) -> None:
        traces = detect_ai_traces(AI_TEXT)
        categories = {trace.category for trace in traces}
        self.assertIn("weak_word", categories)
        self.assertIn("hollow_stack", categories)

    def test_exactly_five_numbered_items_are_detected(self) -> None:
        traces = detect_ai_traces(AI_TEXT)
        self.assertTrue(any(trace.category == "five_item_list" for trace in traces))

    def test_seven_sweeps_find_vague_parent_claim(self) -> None:
        result = run_seven_sweeps("很多家长都说这个平台很靠谱。")
        issues = result["prove_it"] + result["specificity"]
        self.assertTrue(any("很多家长" in issue.quote for issue in issues))

    def test_seven_sweeps_find_vague_time_claim(self) -> None:
        result = run_seven_sweeps("这个方法能省时间，让沟通更加方便。")
        issues = result["specificity"]
        self.assertTrue(any("省时间" in issue.quote for issue in issues))

    def test_seven_sweeps_return_quote_problem_suggestion(self) -> None:
        result = run_seven_sweeps("很多家长觉得方便。")
        issue = result["specificity"][0]
        self.assertTrue(issue.quote)
        self.assertTrue(issue.problem)
        self.assertTrue(issue.suggestion)

    def test_good_reference_gets_high_panel_scores(self) -> None:
        report = review_content(GOOD)
        self.assertGreaterEqual(report.average, 8.0)
        self.assertTrue(all(score >= 7 for score in report.scores.values()))

    def test_ai_like_copy_gets_low_panel_scores(self) -> None:
        report = review_content(AI_TEXT)
        self.assertLess(report.average, 8.0)
        self.assertNotEqual(report.verdict, "pass")
        self.assertTrue(report.low_score_reasons)

    def test_panel_has_three_named_experts(self) -> None:
        report = review_content(GOOD)
        self.assertEqual(
            set(report.scores), {"conversion_copywriter", "target_parent", "compliance_expert"}
        )

    def test_panel_report_contains_improvements(self) -> None:
        report = review_content(AI_TEXT)
        self.assertIsInstance(report.improvement_suggestions, list)
        self.assertTrue(report.improvement_suggestions)

    def test_empty_copy_still_returns_all_sweeps(self) -> None:
        result = run_seven_sweeps("")
        self.assertEqual(
            set(result), {"clarity", "voice", "so_what", "prove_it", "specificity", "emotion", "zero_risk"}
        )
        self.assertTrue(result["emotion"])

    def test_non_string_input_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            detect_ai_traces(None)  # type: ignore[arg-type]

    def test_cli_emits_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "copy.md"
            path.write_text(GOOD, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "quality" / "check.py"), "--file", str(path)],
                cwd=str(ROOT),
                capture_output=True,
                text=False,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
        stdout = completed.stdout.decode("utf-8")
        self.assertIn("# 文案质量门报告", stdout)
        self.assertIn("## 专家评审团", stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
