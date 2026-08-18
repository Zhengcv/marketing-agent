"""七遍文案扫描。

实现故意保持为可解释的启发式规则：每条结果都保留原文片段、问题和可执行建议，
方便人工复核，也不会把质量判定偷偷交给外部模型。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Callable, Dict, List


@dataclass(frozen=True)
class Issue:
    """一条质量问题及其改写提示。"""

    sweep: str
    quote: str
    problem: str
    suggestion: str

    def to_dict(self) -> Dict[str, str]:
        """转成适合 JSON/模板渲染的普通字典。"""
        return asdict(self)


_SWEEP_NAMES = (
    "clarity",
    "voice",
    "so_what",
    "prove_it",
    "specificity",
    "emotion",
    "zero_risk",
)


def _issues_for_matches(
    text: str,
    pattern: str,
    sweep: str,
    problem: str,
    suggestion: str,
) -> List[Issue]:
    """把正则命中转换为去重的问题列表。"""
    found: List[Issue] = []
    seen = set()
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        quote = match.group(0).strip()
        if not quote or quote in seen:
            continue
        seen.add(quote)
        found.append(Issue(sweep, quote, problem, suggestion))
    return found


def clarity_sweep(text: str) -> List[Issue]:
    """检查含糊指代、术语未解释和过长断句。"""
    issues = _issues_for_matches(
        text,
        r"(?:这个|那个|相关|适当|方便|等等|之类的|靠谱)",
        "clarity",
        "表达缺少可核对的对象或标准，读者可能不知道下一步怎么做。",
        "补上对象、判断标准或一个具体动作，例如把“方便”改成“在线查看试讲时间”。",
    )
    for sentence in re.split(r"[。！？!?\n]", text):
        sentence = sentence.strip()
        if len(sentence) >= 60:
            issues.append(
                Issue(
                    "clarity",
                    sentence[:80],
                    "句子过长，多个意思挤在一起，阅读时容易丢失重点。",
                    "拆成两句：先写场景或结论，再写一个动作。",
                )
            )
    return issues


def voice_sweep(text: str) -> List[Issue]:
    """检查品牌口吻中的公文腔、销售腔和突兀语气切换。"""
    issues = _issues_for_matches(
        text,
        r"(?:综上所述|总而言之|值得注意的是|本平台致力于|赋能|全方位)",
        "voice",
        "出现公文或企业宣传腔，与家长聊天式品牌口吻不一致。",
        "改成直接对家长说话的短句，说明你见过的具体情况。",
    )
    if text.count("!") + text.count("！") >= 3:
        issues.append(
            Issue(
                "voice",
                "!" * min(3, text.count("!")) + "！" * min(3, text.count("！")),
                "感叹号过密，语气像硬推销或标题党。",
                "保留一个自然的标点，把强调改为事实或家长可执行的建议。",
            )
        )
    return issues


def so_what_sweep(text: str) -> List[Issue]:
    """检查功能是否接上家长利益，而不是只罗列平台能力。"""
    feature_pattern = r"(?:提供|支持|拥有|匹配|覆盖|采用|实现|进行)[^。！？\n]{0,18}"
    issues: List[Issue] = []
    for match in re.finditer(feature_pattern, text):
        quote = match.group(0).strip()
        tail = text[match.end() : match.end() + 18]
        if not re.search(r"(?:所以|这样|让|帮|省|避免|不用|可以|能让|家长|孩子)", quote + tail):
            issues.append(
                Issue(
                    "so_what",
                    quote,
                    "只说了功能，没有回答“然后呢、对家长有什么用”。",
                    "紧跟一个结果或行动收益，例如“这样家长能先核对证件再约试讲”。",
                )
            )
    return issues


def prove_it_sweep(text: str) -> List[Issue]:
    """检查没有来源或范围的社会证明和夸大断言。"""
    return _issues_for_matches(
        text,
        r"(?:很多家长|大量家长|大家都|用户一致|广受好评|效果显著|非常成功|普遍认为|业内领先|家长都说)",
        "prove_it",
        "这是无来源的数量或效果断言，读者无法验证。",
        "换成可核对的经历、时间、城市或数据来源；没有证据就删掉绝对化表述。",
    )


def specificity_sweep(text: str) -> List[Issue]:
    """检查空泛的数量、时间、效率和质量说法。"""
    return _issues_for_matches(
        text,
        r"(?:省时间|节省时间|很多|不少|很快|尽快|方便|靠谱|专业|优质|效果好|价格实惠|一段时间|多个)",
        "specificity",
        "描述太泛，无法判断节省多少、何时完成或怎样算好。",
        "补充可验证的数字、时长、范围或判断动作；例如“省时间”改为“少跑 4 小时”。",
    )


def emotion_sweep(text: str) -> List[Issue]:
    """检查是否让家长看见真实顾虑、期待或可共情的场景。"""
    emotion_words = r"(?:怕|担心|焦虑|不想学|踩坑|被骗|放心|安心|期待|愿意|纠结|难受|开心|辛苦)"
    if re.search(emotion_words, text):
        return []
    excerpt = text.strip()[:80] or "（空文案）"
    return [
        Issue(
            "emotion",
            excerpt,
            "没有出现家长真实顾虑或期待，内容可能像产品说明书。",
            "开头加入一个具体场景或感受，再给方法；不要用夸张恐吓代替共情。",
        )
    ]


def zero_risk_sweep(text: str) -> List[Issue]:
    """检查 CTA 附近的费用、退款、隐私和行动摩擦。"""
    issues: List[Issue] = []
    # Markdown 范文的发布说明/内部自查不是发送给家长的 CTA。
    body = re.split(r"^\s*##\s+(?:🔍|📱)", text, maxsplit=1, flags=re.MULTILINE)[0]
    cta_matches = list(re.finditer(r"(?:私信|评论区|领取|报名|点击|联系|咨询|加微信)", body))
    for match in cta_matches:
        start = max(0, match.start() - 45)
        end = min(len(body), match.end() + 80)
        context = body[start:end]
        if not re.search(r"(?:怎么|如何|谁付|多少|退|不合适|隐私|不会|无需|自主)", context):
            issues.append(
                Issue(
                    "zero_risk",
                    context.strip(),
                    "CTA 附近没有消除费用、退款、隐私或下一步疑虑。",
                    "补一句低摩擦说明：领取什么、是否收费、信息如何使用，以及不合适怎么办。",
                )
            )
    issues.extend(
        _issues_for_matches(
            text,
            r"(?:先交费|马上付款|限时|名额有限|保证|承诺|不过退|隐藏费用)",
            "zero_risk",
            "出现高压行动或风险承诺，容易让家长产生戒备。",
            "改为自主选择，并明确费用、边界和可验证的流程。",
        )
    )
    return issues


# 便于调用方按“每遍一个函数”的直观命名访问。
SWEEPS: Dict[str, Callable[[str], List[Issue]]] = {
    "clarity": clarity_sweep,
    "voice": voice_sweep,
    "so_what": so_what_sweep,
    "prove_it": prove_it_sweep,
    "specificity": specificity_sweep,
    "emotion": emotion_sweep,
    "zero_risk": zero_risk_sweep,
}


def run_seven_sweeps(text: str) -> Dict[str, List[Issue]]:
    """依次运行七遍并按稳定顺序返回结果。"""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return {name: SWEEPS[name](text) for name in _SWEEP_NAMES}


def flatten_issues(results: Dict[str, List[Issue]]) -> List[Issue]:
    """将七遍结果展平，供报告生成器使用。"""
    return [issue for name in _SWEEP_NAMES for issue in results.get(name, [])]
