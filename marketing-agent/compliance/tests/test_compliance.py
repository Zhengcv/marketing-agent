"""合规审核引擎单元测试。

覆盖 15+ 断言，验证：
    - L1 词库命中各类违禁词（包过/保过/提分/保送名校/清北名师/不过退款/
      押题命中/内部名额/国家级/最高级/第一/唯一/100%通过）
    - L2 否定语境不误杀（"我们并非国家级平台" → warn 不 block）
    - L2 免责声明降级（"提分效果仅供参考" → warn）
    - L3 谐音识别（"帮孩子提fen"）
    - L3 符号绕过识别（"提🌟分"）
    - 安全文案 pass（"陪孩子巩固基础"）

运行::

    python compliance/tests/test_compliance.py
    python -m unittest compliance.tests.test_compliance
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

from compliance.check import check_text  # noqa: E402
from compliance.l1_keyword import run_l1  # noqa: E402
from compliance.l2_context import run_l2  # noqa: E402
from compliance.l3_agent import run_l3  # noqa: E402
from compliance.rules_loader import load_rules  # noqa: E402


# 复用规则集合，避免每条用例重复加载。
_RULES = load_rules()


def _verdict(text: str) -> str:
    """便捷辅助：取文案的 verdict 字符串。"""
    return check_text(text, _RULES).verdict


def _hit_values(text: str) -> list:
    """取文案的 L1 命中词列表（去重保序）。"""
    seen = []
    for h in run_l1(text, _RULES):
        if h.matched not in seen:
            seen.append(h.matched)
    return seen


class TestL1Keyword(unittest.TestCase):
    """L1 词库匹配。"""

    def test_baoguo_baoguo_blocked(self):
        """包过/保过 命中 block。"""
        v = check_text("我们的课程包过保过，一次性通过", _RULES)
        self.assertEqual(v.verdict, "block")
        self.assertIn("包过", _hit_values("我们的课程包过保过"))
        self.assertIn("保过", _hit_values("我们的课程保过"))

    def test_tifen_blocked(self):
        """提分 命中 block。"""
        v = check_text("暑假提分班报名中", _RULES)
        self.assertEqual(v.verdict, "block")

    def test_baosong_mingxiao_blocked(self):
        """保送名校 / 清北名师 命中 block。"""
        v = check_text("保送名校，清北名师授课", _RULES)
        self.assertEqual(v.verdict, "block")
        vals = _hit_values("保送名校，清北名师授课")
        self.assertIn("保送名校", vals)
        self.assertIn("清北名师", vals)

    def test_buguotuikuan_yatimingzhong_blocked(self):
        """不过退款 / 押题命中 命中 block。"""
        v = check_text("不过退款，押题命中率高", _RULES)
        self.assertEqual(v.verdict, "block")

    def test_neibuming_e_blocked(self):
        """内部名额 命中 block。"""
        v = check_text("最后3个内部名额，速抢", _RULES)
        self.assertEqual(v.verdict, "block")
        self.assertIn("内部名额", _hit_values("最后3个内部名额"))

    def test_absolute_terms_blocked(self):
        """国家级/最高级/第一/唯一/100% 全 block。"""
        for term in ["国家级", "最高级", "第一", "唯一", "100%"]:
            v = check_text(f"我们是{term}平台", _RULES)
            self.assertEqual(v.verdict, "block", f"「{term}」应 block，实际 {v.verdict}")

    def test_pass_safe_text(self):
        """安全文案 pass。"""
        v = check_text("陪孩子巩固基础，逐个击破薄弱环节", _RULES)
        self.assertEqual(v.verdict, "pass")


class TestL2Context(unittest.TestCase):
    """L2 语境降级。"""

    def test_negation_downgrade(self):
        """「我们并非国家级平台」→ warn 不 block（否定不误杀）。"""
        v = check_text("我们并非国家级平台", _RULES)
        self.assertEqual(v.verdict, "warn")
        # 原本应命中「国家级」(block)，降级为 warn。
        results = run_l2("我们并非国家级平台", run_l1("我们并非国家级平台", _RULES))
        self.assertTrue(any(r.downgraded for r in results))
        self.assertTrue(all(r.final_severity != "block" for r in results))

    def test_disclaimer_downgrade(self):
        """「提分效果仅供参考」→ warn（免责降级）。"""
        v = check_text("提分效果仅供参考", _RULES)
        self.assertEqual(v.verdict, "warn")
        results = run_l2("提分效果仅供参考", run_l1("提分效果仅供参考", _RULES))
        self.assertTrue(any("disclaimer" in r.reasons for r in results))

    def test_hard_block_not_downgraded_by_negation(self):
        """硬承诺词（包过）在否定语境下也不降级，保持 block。"""
        v = check_text("我们不包过", _RULES)
        self.assertEqual(v.verdict, "block")

    def test_condition_downgrade(self):
        """条件限定语境降级。"""
        v = check_text("如果效果第一则可退", _RULES)
        # 「第一」是 block，前置「如果」属条件语境 → 降级 warn。
        self.assertEqual(v.verdict, "warn")

    def test_question_downgrade(self):
        """疑问语境降级。"""
        v = check_text("我们是第一吗？", _RULES)
        self.assertEqual(v.verdict, "warn")


class TestL3Agent(unittest.TestCase):
    """L3 隐含风险启发式。"""

    def test_homophone_tifen(self):
        """「帮孩子提fen」→ L3 识别谐音。"""
        risks = run_l3("帮孩子提fen")
        self.assertTrue(any(r.kind == "homophone" for r in risks),
                        f"应识别谐音，实际 risks={[r.to_dict() for r in risks]}")
        self.assertEqual(_verdict("帮孩子提fen"), "warn")

    def test_symbol_bypass_star(self):
        """「提🌟分」→ L3 识别符号绕过。"""
        risks = run_l3("提🌟分冲刺")
        self.assertTrue(any(r.kind == "symbol_bypass" for r in risks),
                        f"应识别符号绕过，实际 risks={[r.to_dict() for r in risks]}")
        self.assertEqual(_verdict("提🌟分冲刺"), "warn")

    def test_symbol_bypass_space(self):
        """「提 分」→ L3 识别空格绕过。"""
        risks = run_l3("提 分冲刺")
        self.assertTrue(any(r.kind == "symbol_bypass" for r in risks))

    def test_symbol_bypass_dot(self):
        """「提·分」→ L3 识别点号绕过。"""
        risks = run_l3("提·分")
        self.assertTrue(any(r.kind == "symbol_bypass" for r in risks))

    def test_pinyin_acronym_bg(self):
        """「bg」→ L3 识别拼音首字母代指「包过」。"""
        risks = run_l3("课程bg")
        self.assertTrue(any(r.kind == "pinyin_acronym" and r.target == "包过" for r in risks),
                        f"应识别 bg→包过，实际 risks={[r.to_dict() for r in risks]}")


class TestEndToEnd(unittest.TestCase):
    """端到端 verdict 综合断言。"""

    def test_safe_still_pass(self):
        """多条安全文案均 pass。"""
        for t in [
            "陪孩子巩固基础，逐个击破薄弱环节",
            "周末带娃去公园玩",
            "一起读绘本，培养阅读兴趣",
        ]:
            self.assertEqual(_verdict(t), "pass", f"安全文案「{t}」应 pass")

    def test_block_terms_end_to_end(self):
        """10 条典型违禁文案 verdict 一律 block。"""
        block_texts = [
            "协议班包过，不过退款",
            "保过名校，清北名师",
            "一次性通过，押题命中率高",
            "国家级最高级唯一平台",
            "100%通过率保证",
            "内部名额最后3个",
            "保送名校直通车",
            "必过班火热报名",
            "百分百通过考试",
            "内部题库原题泄露",
        ]
        for t in block_texts:
            self.assertEqual(_verdict(t), "block", f"「{t}」应 block")


if __name__ == "__main__":
    unittest.main(verbosity=2)
