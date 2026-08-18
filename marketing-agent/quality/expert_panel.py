"""三位启发式专家评审文案。

评分不是 LLM 的主观意见，而是由公开信号计算，便于在 CI 中稳定复现。
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from statistics import mean
from typing import Dict, List

from .anti_ai import detect_ai_traces
from .seven_sweeps import run_seven_sweeps, flatten_issues


EXPERT_NAMES = (
    "conversion_copywriter",
    "target_parent",
    "compliance_expert",
)


@dataclass(frozen=True)
class PanelReport:
    """专家团评分结果。"""

    scores: Dict[str, float]
    average: float
    verdict: str
    low_score_reasons: List[str]
    improvement_suggestions: List[str]

    def to_dict(self) -> Dict[str, object]:
        """转成报告字典。"""
        return {
            "scores": dict(self.scores),
            "average": self.average,
            "verdict": self.verdict,
            "low_score_reasons": list(self.low_score_reasons),
            "improvement_suggestions": list(self.improvement_suggestions),
        }


def prepare_publication_text(text: str) -> str:
    """去掉范文中的发布元数据和内部说明，保留实际发布正文。

    普通纯文本不会被改变；带有参考文档章节的 Markdown 则只取“正文”章节，
    避免把合规自查勾选项、拍摄清单或发布时间当成文案质量信号。
    """
    markers = ("## 🔍 合规自查", "## 📱 评论区自留")
    body = text.split("## 📝 正文", 1)[-1]
    for marker in markers:
        body = body.split(marker, 1)[0]
    return body


# 兼容内部旧调用；新代码使用公开名称。
def _publication_text(text: str) -> str:
    return prepare_publication_text(text)


def _has_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _bounded(score: float) -> float:
    return round(max(1.0, min(10.0, score)), 1)


def _conversion_score(text: str, issue_count: int) -> float:
    score = 5.5
    if re.search(r"[？?]", text[:260]):
        score += 0.8  # 痛点式 hook
    if re.search(r"(?:最怕什么|你踩过|花了钱|不想学)", text[:260]):
        score += 0.7  # 无问号时仍识别口语化痛点 hook
    if _has_any(text, [r"评论区", r"私信", r"领取", r"了解"]):
        score += 1.0
    if _has_any(text, [r"帮", r"让", r"避免", r"不用", r"可以"]):
        score += 0.8
    # 分节标题和可执行清单是发布文案的转化结构信号；仅有裸编号不加分。
    rich_sections = len(re.findall(r"(?:\*\*[1-9][^\n]{0,24}\*\*|[一二三四五六七八九]️⃣)", text))
    if rich_sections >= 3:
        score += 1.0
    if re.search(r"(?:问清楚|核对|观察|确认|问一句|先让)", text):
        score += 0.5
    if len(text) >= 120:
        score += 0.5
    score -= min(2.5, issue_count * 0.25)
    return _bounded(score)


def _parent_score(text: str, issue_count: int) -> float:
    score = 5.6
    if re.search(r"(?:我帮|我遇到|我见过|上个月|一个妈妈|一个家长|家长)", text):
        score += 1.3
    if re.search(r"(?:家长|孩子|老师|试讲|担心|怕|不想学)", text):
        score += 1.0
    if re.search(r"\d", text):
        score += 0.6
    if re.search(r"(?:L1|L2|L3|信息费|课时费)", text):
        score += 0.6
    score -= min(2.5, issue_count * 0.2)
    return _bounded(score)


def _compliance_score(text: str, ai_count: int, issue_count: int) -> float:
    score = 7.0
    if re.search(r"(?:信息中介|信息撮合|老师单边付|家长只付课时费)", text):
        score += 1.0
    # “第一个坑/第一步”是结构编号，不是广告法绝对化承诺。
    if re.search(r"(?:提分|保过|升学率|名师|(?<!第)第一(?!个|步|条|项)|唯一|加微信|免费试课)", text):
        score -= 3.0
    score -= min(2.5, ai_count * 0.15 + issue_count * 0.1)
    return _bounded(score)


def review_content(text: str) -> PanelReport:
    """按转化、家长可信度、合规三个人设打分并给出 verdict。"""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    publication_text = _publication_text(text)
    sweeps = run_seven_sweeps(publication_text)
    issue_count = len(flatten_issues(sweeps))
    ai_count = len(detect_ai_traces(publication_text))
    scores = {
        "conversion_copywriter": _conversion_score(publication_text, issue_count),
        "target_parent": _parent_score(publication_text, issue_count),
        "compliance_expert": _compliance_score(publication_text, ai_count, issue_count),
    }
    average = round(mean(scores.values()), 2)
    reasons: List[str] = []
    suggestions: List[str] = []
    labels = {
        "conversion_copywriter": "转化文案师",
        "target_parent": "目标家长视角",
        "compliance_expert": "合规专家",
    }
    for name, score in scores.items():
        if score < 7:
            reasons.append(f"{labels[name]}评分 {score:.1f}，低于 7 分门槛。")
    if ai_count:
        reasons.append(f"检测到 {ai_count} 条 AI 痕迹，削弱自然可信度。")
        suggestions.append("删掉套话和空洞形容词，用真实经历、数字和可验证动作替换。")
    if not re.search(r"(?:评论区|私信|领取|了解)", publication_text):
        reasons.append("没有清晰的低摩擦行动引导。")
        suggestions.append("结尾说明家长下一步能做什么，并交代领取内容和费用边界。")
    if not re.search(r"(?:我帮|我遇到|一个妈妈|一个家长|帮家长)", publication_text):
        suggestions.append("补充至少一段具体到人物、城市和处理方式的第一人称经历。")
    if not suggestions:
        suggestions.append("继续人工核对事实、数字和发布平台的合规要求。")
    verdict = "pass" if all(score >= 7 for score in scores.values()) and average >= 8 else "warn"
    if any(score < 5 for score in scores.values()):
        verdict = "fail"
    return PanelReport(scores, average, verdict, reasons, suggestions)
