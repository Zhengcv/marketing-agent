"""中文文案反 AI 痕迹检测。

这里只做可解释的文本规则，不模拟平台检测器，也不依赖第三方或 LLM。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class AITrace:
    """命中的 AI 痕迹。"""

    category: str
    quote: str
    problem: str
    suggestion: str

    def to_dict(self) -> Dict[str, str]:
        """转成普通字典。"""
        return asdict(self)


_FILLER_PHRASES = (
    "在当今社会",
    "值得注意的是",
    "总而言之",
    "综上所述",
    "首先其次最后",
    "首先、其次、最后",
    "不可否认",
    "显而易见",
)
_WEAK_WORDS = ("非常", "很", "真的", "挺", "比较", "进行", "利用")
_HOLLOW_STACKS = ("高效便捷", "优质专业", "一站式", "全方位", "安全可靠", "省心省力")


def _phrase_traces(text: str, phrases: Iterable[str]) -> List[AITrace]:
    traces: List[AITrace] = []
    seen = set()
    for phrase in phrases:
        if phrase in text and phrase not in seen:
            seen.add(phrase)
            traces.append(
                AITrace(
                    "filler_phrase",
                    phrase,
                    "这是常见的 AI 过渡或套话，不能增加事实信息。",
                    "删掉铺垫，直接从家长的具体场景或问题开头。",
                )
            )
    return traces


def _weak_word_traces(text: str) -> List[AITrace]:
    """按语境命中弱词，避免把“很多平台”误报成 AI 填充。"""
    traces: List[AITrace] = []
    for word in _WEAK_WORDS:
        for match in re.finditer(re.escape(word), text):
            start = max(0, match.start() - 8)
            end = min(len(text), match.end() + 8)
            context = text[start:end]
            # “很多家长/平台”是待 Prove It 扫描的数量断言，不属于弱词。
            if word == "很" and re.match(r"很[多少]", text[match.start() : match.start() + 2]):
                continue
            # “真的”在“认证才是真的”中是对证据真实性的有效对比。
            if word == "真的" and re.search(r"认证.{0,4}才是", text[max(0, match.start() - 12) : match.end() + 8]):
                continue
            traces.append(
                AITrace(
                    "weak_word",
                    match.group(0),
                    "弱化词让判断变得空泛，且容易形成机械的 AI 语气。",
                    f"结合上下文改写“{context}”为可验证的动作、数量或直接结论。",
                )
            )
    return traces


def _hollow_traces(text: str) -> List[AITrace]:
    return [
        AITrace(
            "hollow_stack",
            phrase,
            "空洞形容词堆砌，没有说明具体怎么做或带来什么结果。",
            "拆成事实和动作，例如写明认证层级、费用承担方或试讲步骤。",
        )
        for phrase in _HOLLOW_STACKS
        if phrase in text
    ]


def _five_item_trace(text: str) -> List[AITrace]:
    """识别恰好五个连续编号/项目符号，避免 AI 默认清单感。"""
    numbered = re.findall(r"(?m)^\s*(?:[1-5]|[一二三四五])[\.、)）]\s*\S+", text)
    if len(numbered) == 5:
        return [
            AITrace(
                "five_item_list",
                "\n".join(numbered),
                "恰好 5 项的整齐清单容易显出默认 AI 模板痕迹。",
                "改成 4 或 6 项，或把其中一项改为真实经历/场景，而不是机械补齐。",
            )
        ]
    return []


def detect_ai_traces(text: str) -> List[AITrace]:
    """返回所有命中的 AI 痕迹，按规则组稳定排序。"""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    traces = _phrase_traces(text, _FILLER_PHRASES)
    traces.extend(_weak_word_traces(text))
    traces.extend(_hollow_traces(text))
    traces.extend(_five_item_trace(text))
    return traces


def ai_trace_summary(text: str) -> Dict[str, object]:
    """返回报告层使用的命中数、分类和详情。"""
    traces = detect_ai_traces(text)
    counts: Dict[str, int] = {}
    for trace in traces:
        counts[trace.category] = counts.get(trace.category, 0) + 1
    return {"total": len(traces), "counts": counts, "traces": traces}
