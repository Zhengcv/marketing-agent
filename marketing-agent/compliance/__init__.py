"""营销内容合规审核引擎包。

三级审核架构：
    L1 词库匹配（rules_loader + l1_keyword）
        —— 对接 rules.json 2104 条规则，关键词子串命中 + 正则命中。
    L2 语境降级（l2_context）
        —— 对 L1 命中词回看前 10 字，识别否定/免责/条件/引用/疑问/
           比较/科普 七维语境，按需将 block 降为 warn。
    L3 Agent 研判（l3_agent，启发式，不依赖 LLM）
        —— 识别谐音替代、拼音首字母、表情符号绕过等隐含风险。

统一入口：``python -m compliance.check`` 或直接 ``python compliance/check.py``。

零第三方依赖，仅使用 Python 3.10+ 标准库。
"""

from .rules_loader import load_rules, load_rules_grouped
from .l1_keyword import run_l1, L1Hit
from .l2_context import run_l2, L2Result
from .l3_agent import run_l3, L3Risk

# check 作为 CLI 入口，按需懒导入，避免 `python -m compliance.check` 时
# 因 __init__ 已 import check 而产生 runpy 循环加载告警。


def check_text(text, rules=None):
    """对文案执行 L1→L2→L3 三级审核（懒加载 check 模块）。"""
    from .check import check_text as _ct
    return _ct(text, rules)


def Verdict(*args, **kwargs):  # noqa: N802 - 兼容导出
    from .check import Verdict as _V
    return _V(*args, **kwargs)


__all__ = [
    "load_rules",
    "load_rules_grouped",
    "run_l1",
    "L1Hit",
    "run_l2",
    "L2Result",
    "run_l3",
    "L3Risk",
    "check_text",
    "Verdict",
]
