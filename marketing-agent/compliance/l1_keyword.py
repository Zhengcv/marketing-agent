"""L1 词库匹配层。

职责：
    遍历 ``rules_loader`` 加载的扁平规则列表，对输入文案执行
    - keyword 规则：中文子串匹配（``value in text``）；
    - regex 规则：``re.search``，命中即记录。

对每条命中产出 :class:`L1Hit`，包含命中词、规则 id（category+序号）、
法条、严重度、改写建议、文本片段（命中处前后各 10 字上下文）。
"""

from __future__ import annotations

import re
from typing import List

from .rules_loader import PatternRule, load_rules


class L1Hit:
    """L1 命中记录。

    Attributes:
        matched: 实际命中的文本片段（keyword 取规则 value，regex 取 match.group(0)）。
        category: 规则组 id。
        law: 法条。
        severity: 原始严重度（未经 L2 降级）。
        suggestion: 改写建议。
        snippet: 命中处上下文片段（前 10 字 + 命中词 + 后 10 字）。
        start: 命中在原文中的起始下标。
        end: 命中在原文中的结束下标。
        rule_type: "keyword" | "regex"。
        rule_value: 规则原始 value（关键词或正则串）。
    """

    def __init__(
        self,
        matched: str,
        category: str,
        law: str,
        severity: str,
        suggestion: str,
        snippet: str,
        start: int,
        end: int,
        rule_type: str,
        rule_value: str,
    ) -> None:
        self.matched = matched
        self.category = category
        self.law = law
        self.severity = severity
        self.suggestion = suggestion
        self.snippet = snippet
        self.start = start
        self.end = end
        self.rule_type = rule_type
        self.rule_value = rule_value

    def to_dict(self) -> dict:
        """转字典，便于 JSON 序列化。"""
        return {
            "matched": self.matched,
            "category": self.category,
            "law": self.law,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "snippet": self.snippet,
            "start": self.start,
            "end": self.end,
            "rule_type": self.rule_type,
            "rule_value": self.rule_value,
        }

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"L1Hit(matched={self.matched!r}, category={self.category!r}, "
            f"severity={self.severity!r}, snippet={self.snippet!r})"
        )


def _make_snippet(text: str, start: int, end: int, window: int = 10) -> str:
    """生成命中处上下文片段：前 window 字 + 命中 + 后 window 字。

    用 ``…`` 标记截断，方便人眼快速定位。
    """
    pre = text[max(0, start - window): start]
    post = text[end: end + window]
    prefix = "…" if start - window > 0 else ""
    suffix = "…" if end + window < len(text) else ""
    return f"{prefix}{pre}【{text[start:end]}】{post}{suffix}"


def run_l1(text: str, rules: List[PatternRule] | None = None) -> List[L1Hit]:
    """对文案执行 L1 词库匹配。

    Args:
        text: 待审核文案。
        rules: 规则列表；默认调用 :func:`rules_loader.load_rules` 全量加载。

    Returns:
        命中列表，按规则在列表中的顺序排列。
    """
    if rules is None:
        rules = load_rules()

    hits: List[L1Hit] = []
    for rule in rules:
        value = rule.get("value", "")
        if not value:
            continue
        rtype = rule.get("type", "keyword")

        if rtype == "keyword":
            # 中文子串匹配；记录所有出现位置。
            idx = 0
            while True:
                pos = text.find(value, idx)
                if pos == -1:
                    break
                hits.append(
                    L1Hit(
                        matched=value,
                        category=rule["category"],
                        law=rule["law"],
                        severity=rule["severity"],
                        suggestion=rule["suggestion"],
                        snippet=_make_snippet(text, pos, pos + len(value)),
                        start=pos,
                        end=pos + len(value),
                        rule_type="keyword",
                        rule_value=value,
                    )
                )
                idx = pos + len(value)
        elif rtype == "regex":
            # 正则匹配；命中即记录首个匹配。
            try:
                m = re.search(value, text)
            except re.error:
                # 规则库可能存在非法正则，跳过并保留可审计性。
                continue
            if m:
                hits.append(
                    L1Hit(
                        matched=m.group(0),
                        category=rule["category"],
                        law=rule["law"],
                        severity=rule["severity"],
                        suggestion=rule["suggestion"],
                        snippet=_make_snippet(text, m.start(), m.end()),
                        start=m.start(),
                        end=m.end(),
                        rule_type="regex",
                        rule_value=value,
                    )
                )
    return hits
