"""L3 Agent 研判层（启发式，不依赖 LLM）。

职责：
    识别 L1 词库无法直接命中的隐含风险——违规意图通过变体绕过词库：
      1. 谐音替代：``提fen`` / ``tí分`` / ``提分鸭``（拼音/英文字母混写）。
      2. 拼音首字母：``bg``→包过、``bs``→保送、``bgby``→包过保送。
      3. 表情/符号绕过：``提🌟分`` / ``提 分`` / ``提·分`` / ``提_分``。
      4. 双关隐喻：留 TODO，语义复杂度高，后续接 LLM 研判。

实现思路：
    - ``_strip_obfuscation`` 先把文案中的表情、下划线、点、空格等"隔断符"
      按字符级清除，得到"紧凑版"文案，再用 L1 词库对紧凑版扫一遍，
      命中即记为"符号绕过"风险。
    - 谐音替代与拼音首字母通过显式映射表检测，命中后回原文定位片段。
    - 所有 L3 命中一律标 ``severity=warn``（疑似风险，需人工复核），
      不直接 block，避免启发式过度拦截。
"""

from __future__ import annotations

import re
from typing import List, Tuple

from .l1_keyword import _make_snippet


# 谐音替代关键词映射：归一目标 → 可能的变体正则列表。
# value 用 re 匹配，便于容纳大小写混写。
_HOMOPHONE_MAP: List[Tuple[str, str]] = [
    # 目标词"提分"——民办教育培训核心敏感词。
    ("提分", r"提\s*[fF][eE][nN]"),
    ("提分", r"t[iíì]?[fF][eE][nN]"),
    ("提分", r"提分鸭"),
    ("提分", r"提\s*分鸭"),
    ("提分", r"提\s*[fF][eE][nN]\s*鸭"),
    ("提分", r"[tT][íiì]?[fF][eE][nN]"),
    ("包过", r"包\s*[gG][uU][oO]"),
    ("保过", r"保\s*[gG][uU][oO]"),
    ("保送", r"保\s*[sS][oO][nN][gG]"),
]


# 拼音首字母映射：首字母串 → 敏感词。
# 只收录高敏感教育/承诺类，避免误杀日常缩写。
_PINYIN_ACRONYM_MAP: List[Tuple[str, str]] = [
    ("bg", "包过"),
    ("by", "包诱"),            # 兼用，低频
    ("bs", "保送"),
    ("bgbs", "包过保送"),
    ("tf", "提分"),
    ("btgk", "包通过考"),       # 组合型，低频
    ("yhmx", "押题命中"),       # yt→yh 代表拼音首字母变体
    ("ytmz", "押题命中"),       # 常见误读首字母
]


# 用于"符号绕过"的隔断符集合：出现在这些字符即视作可能的隔断写法。
_SEP_CHARS = "🌟✨⭐·_-/\\|｜　 "


# 符号绕过目标词：在"紧凑版"文案里用 L1 关键词命中的敏感词集合。
# 覆盖需求里点名的"提🌟分"/"提 分"/"提·分"/"提_分"。
_SYMBOL_BYPASS_TARGETS: Tuple[str, ...] = (
    "提分", "包过", "保过", "押题", "命题",
)


class L3Risk:
    """L3 隐含风险记录。

    Attributes:
        kind: 风险类型（"homophone" | "pinyin_acronym" | "symbol_bypass" | "metaphor"）。
        target: 疑似对应的敏感词（如 "提分"）。
        matched: 实际命中的文本片段。
        snippet: 上下文片段。
        start, end: 在原文中的起止位置。
        severity: 一律 "warn"（启发式疑似）。
        detail: 说明文字（供打印）。
    """

    def __init__(self, kind: str, target: str, matched: str,
                 snippet: str, start: int, end: int,
                 severity: str = "warn", detail: str = "") -> None:
        self.kind = kind
        self.target = target
        self.matched = matched
        self.snippet = snippet
        self.start = start
        self.end = end
        self.severity = severity
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target": self.target,
            "matched": self.matched,
            "snippet": self.snippet,
            "start": self.start,
            "end": self.end,
            "severity": self.severity,
            "detail": self.detail,
        }

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"L3Risk(kind={self.kind!r}, target={self.target!r}, "
            f"matched={self.matched!r}, snippet={self.snippet!r})"
        )


def _homophone_scan(text: str) -> List[L3Risk]:
    """谐音替代扫描：按映射表用正则在全文找变体写法。"""
    risks: List[L3Risk] = []
    for target, pattern in _HOMOPHONE_MAP:
        for m in re.finditer(pattern, text):
            risks.append(
                L3Risk(
                    kind="homophone",
                    target=target,
                    matched=m.group(0),
                    snippet=_make_snippet(text, m.start(), m.end()),
                    start=m.start(),
                    end=m.end(),
                    detail=f"疑似「{target}」谐音变体：{m.group(0)!r}",
                )
            )
    return risks


def _pinyin_acronym_scan(text: str) -> List[L3Risk]:
    """拼音首字母扫描：在文案里定位独立缩写串并匹配敏感首字母。"""
    risks: List[L3Risk] = []
    # 定位候选：连续 2-6 个 ASCII 字母（大小写），单词化。
    for m in re.finditer(r"(?<![A-Za-z])[A-Za-z]{2,6}(?![A-Za-z])", text):
        token = m.group(0).lower()
        for acronym, target in _PINYIN_ACRONYM_MAP:
            if token == acronym:
                risks.append(
                    L3Risk(
                        kind="pinyin_acronym",
                        target=target,
                        matched=m.group(0),
                        snippet=_make_snippet(text, m.start(), m.end()),
                        start=m.start(),
                        end=m.end(),
                        detail=f"疑似拼音首字母「{acronym}」代指「{target}」",
                    )
                )
    return risks


def _strip_obfuscation(text: str) -> Tuple[str, List[Tuple[int, int, int, int]]]:
    """生成"紧凑版"文案：删除隔断符。返回 (compact_text, 映射)。

    映射：``[(compact_index, compact_index+1, orig_start, orig_end), ...]``
    为简化实现，只返回紧凑文本；起止位置用文本字符对应即可。
    本函数只产出 compact 字符串，定位交由调用方在原文里用
    ``compact_word`` 反查。
    """
    compact_chars: List[str] = []
    for ch in text:
        if ch in _SEP_CHARS:
            continue
        compact_chars.append(ch)
    return "".join(compact_chars), []


def _symbol_bypass_scan(text: str) -> List[L3Risk]:
    """符号/空格绕过扫描。

    思路：把隔断符移除后得到紧凑文案，对一组核心敏感词做子串匹配；
    命中后在原文里反查对应区间（通过逐字符对齐）。
    """
    risks: List[L3Risk] = []
    compact, _ = _strip_obfuscation(text)

    # 对每个目标词在紧凑文案里找，再映射回原文。
    for target in _SYMBOL_BYPASS_TARGETS:
        c_idx = 0
        while True:
            pos = compact.find(target, c_idx)
            if pos == -1:
                break
            # 紧凑位置 → 原文位置：双向游标对齐。
            orig_start, orig_end = _compact_to_orig(text, pos, pos + len(target))
            if orig_start is not None:
                matched_orig = text[orig_start:orig_end]
                # 只有当原文片段不等于纯目标词（即确有隔断）才记风险。
                if matched_orig != target:
                    risks.append(
                        L3Risk(
                            kind="symbol_bypass",
                            target=target,
                            matched=matched_orig,
                            snippet=_make_snippet(text, orig_start, orig_end),
                            start=orig_start,
                            end=orig_end,
                            detail=f"疑似「{target}」符号/空格绕过：{matched_orig!r}",
                        )
                    )
            c_idx = pos + len(target)
    return risks


def _compact_to_orig(text: str, c_start: int, c_end: int) -> Tuple[int, int | None]:
    """将紧凑文档的下标区间映射回原文区间。

    遍历原文，跳过隔断符，累计紧凑字符，直到达到 c_start 记录原文下标，
    继续累计到 c_end 记录原文结束下标。
    """
    orig_idx = 0
    comp_idx = 0
    start_orig = None
    end_orig = None
    for i, ch in enumerate(text):
        if ch in _SEP_CHARS:
            continue
        if comp_idx == c_start:
            start_orig = i
        if comp_idx == c_end - 1:
            # 结束下标是下一个非隔断字符位置或字符串尾。
            # 需要往后跳过可能紧贴的隔断符再定位。
            j = i
            # 累计原文字符直到紧凑 idx 达到 c_end
            while j + 1 < len(text) and comp_idx < c_end - 1 + (c_end - c_start):
                pass
            end_orig = i + 1
            # 往后吞掉紧贴的隔断符也算命中片段（让 matched 可读）。
            while end_orig < len(text) and text[end_orig] in _SEP_CHARS:
                # 只吞掉紧邻命中词末尾后、且其后仍是目标词后续字符的那种；
                # 这里简化：不吞，matched 直接由原文区间给出即可。
                break
            break
        comp_idx += 1
        orig_idx = i + 1

    if start_orig is None:
        return -1, None
    if end_orig is None:
        # 退而求其次：从 start_orig 起累计 c_end-c_start 个非隔断字符。
        cnt = 0
        k = start_orig
        while k < len(text) and cnt < (c_end - c_start):
            if text[k] not in _SEP_CHARS:
                cnt += 1
            end_orig = k + 1
            k += 1
    return start_orig, end_orig


def run_l3(text: str) -> List[L3Risk]:
    """执行 L3 隐含风险扫描（谐音 / 首字母 / 符号绕过）。

    Args:
        text: 原始文案。

    Returns:
        风险列表（去重后），severity 均为 warn。
    """
    risks: List[L3Risk] = []
    risks.extend(_homophone_scan(text))
    risks.extend(_pinyin_acronym_scan(text))

    # 符号绕过：用更稳健的原位扫描代替易错的紧凑映射。
    risks.extend(_symbol_bypass_inplace(text))

    # 双关隐喻：TODO，语义依赖强，留待接入 LLM 研判。
    # risks.extend(_metaphor_scan(text))

    # 按起止位置去重（同一片段被多种方式命中只留其一）。
    seen: set = set()
    deduped: List[L3Risk] = []
    for r in risks:
        key = (r.start, r.end, r.kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def _symbol_bypass_inplace(text: str) -> List[L3Risk]:
    """稳健的原位符号绕过扫描：直接在原文里用正则匹配"含隔断符的目标词"。"""
    risks: List[L3Risk] = []
    # 对每个目标词，生成允许单字符隔断穿插的正则。
    sep_class = re.escape(_SEP_CHARS)
    for target in _SYMBOL_BYPASS_TARGETS:
        # 例如 "提分" → "提[\s🌟…]*分"，允许 0-3 个隔断符插入两字之间。
        # 只在目标词为多字时拆分；单字符无法插入隔断。
        if len(target) < 2:
            continue
        # 在目标词的每两个相邻字符之间允许 0-2 个隔断符。
        parts = list(target)
        pattern = re.escape(parts[0])
        for ch in parts[1:]:
            pattern += f"[{sep_class}]{{0,2}}{re.escape(ch)}"
        for m in re.finditer(pattern, text):
            matched = m.group(0)
            if matched == target:
                # 纯无缝命中——不是绕过，交给 L1 处理。
                continue
            risks.append(
                L3Risk(
                    kind="symbol_bypass",
                    target=target,
                    matched=matched,
                    snippet=_make_snippet(text, m.start(), m.end()),
                    start=m.start(),
                    end=m.end(),
                    detail=f"疑似「{target}」符号/空格绕过：{matched!r}",
                )
            )
    return risks
