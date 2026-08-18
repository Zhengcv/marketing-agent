"""L2 语境降级层。

职责：
    对 L1 命中词回看其前 10 字上下文，识别七类可降级语境，
    对原本 severity=block 的命中按规则降级为 warn：
      1. 否定语境：不是/并非/不代表/没有/不能承诺/不保证 → block 降 warn
      2. 免责声明：仅供参考/具体以...为准/以实际为准 → 降级
      3. 条件限定：如果/若/可能/视情况/在...前提下 → 降级
      4. 引用语境：据...报道/有人说/网友说/据报道 → 降级
      5. 疑问语境：含 ？/吗/会不会/是否 → 降级
      6. 比较语境：比...更/相比/相较于 → 降级
      7. 科普语境：研究表明/数据显示/据研究 → 降级

说明：
    - 降级只把 block 降为 warn；本身是 warn 的保持 warn。
    - 一条命中只要命中任意一个降级语境即降级，并把命中的所有语境原因收集返回。
    - 降级是"软"判断：宁可漏降（仍 warn 提示）也不误放过硬违禁；
      对部分敏感类别（industry-education 的"包过/保过/押题命中/内部名额"
      等"硬承诺"词）即便在否定语境下也保持 block——这些词出现在否定句里
      仍是高风险信号，由人工复核。
"""

from __future__ import annotations

import re
from typing import List

from .l1_keyword import L1Hit


# 七维降级语境定义：每项 (维度名, 是否命中该维度的判断函数)。
# 命中函数接收 (前置上下文 pre, 整句片段 snippet) 返回是否降级。

# 否定语境关键词：紧贴命中词前出现否定词即触发。
_NEGATION_WORDS = (
    "不是", "并非", "不代表", "没有", "不能承诺", "不保证",
    "不能保证", "无法保证", "不会", "未能", "不曾", "无",
    "不", "非",
)

# 免责声明关键词（可出现在前置 10 字内）。
_DISCLAIMER_WORDS = (
    "仅供参考", "具体以", "以实际", "以官方", "以最终",
    "以合同", "以页面", "以实物", "不构成", "不作为",
)

# 条件限定关键词。
_CONDITION_WORDS = (
    "如果", "若", "可能", "视情况", "取决于", "在……前提",
    "在...前提", "前提下", "理论上", "理想情况",
)

# 引用语境关键词。
_CITATION_WORDS = (
    "据", "报道", "有人说", "网友说", "有网友", "有用户",
    "据称", "传闻", "据传",
)

# 比较语境关键词。
_COMPARISON_WORDS = (
    "比", "相比", "相较于", "相比于", "相较", "相对于",
)

# 科普语境关键词。
_SCIENCE_WORDS = (
    "研究表明", "数据显示", "据研究", "实验表明", "调查表明",
    "统计显示", "文献",
)


# 硬承诺词白名单：即使否定语境也不降级。
# 主要针对教育行业"对结果的承诺"，这些短语出现在文案里本身就是高风险示意，
# 否定语境也难以洗清（"我们不包过" 仍属敏感营销口径）。
_HARD_BLOCK_VALUES = {
    "包过", "保过", "必过", "一次性通过", "百分百通过", "包上岸",
    "保证上岸", "押题命中", "原题泄露", "内部名额", "内部题库",
    "命题人",
}


def _check_negation(pre: str, _snippet: str, _post: str = "") -> bool:
    """否定语境：前置 10 字内出现否定词。"""
    return any(w in pre for w in _NEGATION_WORDS)


def _check_disclaimer(pre: str, _snippet: str, post: str = "") -> bool:
    """免责声明：前置或后置 10 字内出现免责关键词。"""
    return any(w in pre for w in _DISCLAIMER_WORDS) or any(
        w in post for w in _DISCLAIMER_WORDS
    )


def _check_condition(pre: str, _snippet: str, post: str = "") -> bool:
    """条件限定：前置或后置 10 字内出现条件关键词。"""
    return any(w in pre for w in _CONDITION_WORDS) or any(
        w in post for w in _CONDITION_WORDS
    )


def _check_citation(pre: str, _snippet: str, _post: str = "") -> bool:
    """引用语境：前置 10 字内出现引用关键词。"""
    # "据" 需后跟报道/研究等才更准，这里为防漏判，单独处理"据"后跟非停用词。
    if any(w in pre for w in _CITATION_WORDS):
        return True
    # "据报道/据研究" 这种双字组合已在上方覆盖。
    return False


def _check_question(_pre: str, snippet: str, _post: str = "") -> bool:
    """疑问语境：命中片段所在句含问号/吗/会不会/是否等。"""
    # 通过 snippet（命中处 ±10 字）判断疑问。
    markers = ("？", "?", "吗", "会不会", "是否", "么", "嘛")
    return any(m in snippet for m in markers)


def _check_comparison(pre: str, snippet: str, _post: str = "") -> bool:
    """比较语境：前置 10 字或命中片段内出现比较关键词。"""
    return any(w in pre for w in _COMPARISON_WORDS) or any(
        w in snippet for w in _COMPARISON_WORDS
    )


def _check_science(pre: str, _snippet: str, post: str = "") -> bool:
    """科普语境：前置或后置 10 字内出现科普关键词。"""
    return any(w in pre for w in _SCIENCE_WORDS) or any(
        w in post for w in _SCIENCE_WORDS
    )


# 维度表：(维度名, 检查函数)
_DIMENSIONS = (
    ("negation", _check_negation),
    ("disclaimer", _check_disclaimer),
    ("condition", _check_condition),
    ("citation", _check_citation),
    ("question", _check_question),
    ("comparison", _check_comparison),
    ("science", _check_science),
)


class L2Result:
    """L2 对单条命中的降级判定结果。

    Attributes:
        hit: 对应的 L1 命中。
        downgraded: 是否被降级（block → warn）。
        original_severity: 原始严重度。
        final_severity: 最终严重度（降级后）。
        reasons: 命中的降级语境维度名列表（如 ["negation", "disclaimer"]）。
    """

    def __init__(self, hit: L1Hit, downgraded: bool,
                 original_severity: str, final_severity: str,
                 reasons: List[str]) -> None:
        self.hit = hit
        self.downgraded = downgraded
        self.original_severity = original_severity
        self.final_severity = final_severity
        self.reasons = reasons

    @property
    def matched(self) -> str:
        return self.hit.matched

    @property
    def severity(self) -> str:
        """最终生效的严重度（供 check.py 判 verdict）。"""
        return self.final_severity

    def to_dict(self) -> dict:
        return {
            "matched": self.hit.matched,
            "category": self.hit.category,
            "law": self.hit.law,
            "original_severity": self.original_severity,
            "final_severity": self.final_severity,
            "downgraded": self.downgraded,
            "reasons": self.reasons,
            "suggestion": self.hit.suggestion,
            "snippet": self.hit.snippet,
        }


def _pre_context(text: str, start: int, window: int = 10) -> str:
    """取命中起始位置前的 window 字。"""
    return text[max(0, start - window): start]


def _post_context(text: str, end: int, window: int = 10) -> str:
    """取命中结束位置后的 window 字（免责/条件/科普常后置）。"""
    return text[end: end + window]


def run_l2(text: str, l1_hits: List[L1Hit]) -> List[L2Result]:
    """对 L1 命中列表逐一判定降级。

    降级语境判定同时考虑命中词的前 10 字与后 10 字：
        - 否定/引用/比较 侧重前置（"不是…/据…/比…"通常在前）；
        - 免责/条件/科普 侧重后置（"…仅供参考/…如果…/…研究表明"
          可紧随敏感词之后，如"提分效果仅供参考"）。
    任一维度命中即降级。

    Args:
        text: 原始文案。
        l1_hits: L1 命中列表。

    Returns:
        与 l1_hits 等长的 :class:`L2Result` 列表，顺序一致。
    """
    results: List[L2Result] = []
    for hit in l1_hits:
        pre = _pre_context(text, hit.start)
        post = _post_context(text, hit.end)
        snippet = hit.snippet

        reasons: List[str] = []
        for name, fn in _DIMENSIONS:
            try:
                if fn(pre, snippet, post):
                    reasons.append(name)
            except Exception:
                # 降级判定不应影响主流程；任意维度异常忽略。
                continue

        original = hit.severity
        # 硬承诺词即便有降级语境也不降级。
        is_hard = hit.matched in _HARD_BLOCK_VALUES or hit.rule_value in _HARD_BLOCK_VALUES
        should_downgrade = bool(reasons) and original == "block" and not is_hard

        final = "warn" if should_downgrade else original
        downgraded = should_downgrade or (bool(reasons) and original == "warn")
        results.append(
            L2Result(
                hit=hit,
                downgraded=downgraded,
                original_severity=original,
                final_severity=final,
                reasons=reasons,
            )
        )
    return results
