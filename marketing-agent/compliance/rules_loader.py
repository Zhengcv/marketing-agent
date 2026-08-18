"""规则加载器。

从 ``docs/marketing/design/rules.json`` 加载 2104 条合规规则，
并按 ``category``（即 rule_group 的 id）分组。

数据结构约定（rules.json 片段）::

    {
      "version": "4.10",
      "rule_groups": [
        {
          "id": "adlaw-absolute",          # 组标识，用作 category
          "name": "广告法绝对化用语",
          "law": "《广告法》第九条第三项",
          "severity": "block",              # 组级严重度
          "description": "...",
          "triggers": ["..."],              # 可选，行业组才有
          "patterns": [
            {"type":"keyword","value":"国家级","suggestion":"..."},
            {"type":"regex","value":"\\d+天...","suggestion":"..."}
          ]
        },
        ...
      ]
    }

本模块对每条 pattern 补一个 ``category``（等于所在组的 id），
并把组级 ``law`` / ``severity`` 平铺到 pattern 上，
形成扁平的规则字典列表，便于 L1 直接遍历。
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Dict, List, TypedDict


class PatternRule(TypedDict):
    """扁平化后的单条规则。"""

    category: str          # 所属规则组 id（如 "adlaw-absolute"）
    group_name: str        # 规则组中文名
    law: str               # 法条
    severity: str          # "block" | "warn"
    type: str              # "keyword" | "regex"
    value: str             # 关键词或正则字符串
    suggestion: str        # 改写建议


# 默认规则文件路径（相对仓库根）。
# 解析为：本文件向上四级回到仓库根，再下探到 docs/marketing/design/rules.json。
_DEFAULT_RULES_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "docs", "marketing", "design", "rules.json",
    )
)


# 平台教育行业补充规则。
# 说明：rules.json v4.10 是通用电商内容合规库，其 industry-education 组
# 未覆盖家教平台核心敏感词「提分」（承诺提分效果属《广告法》第二十四条
# 教育培训不得承诺通过考试/效果的延伸）。本补充规则集不修改 docs/ 下已定
# 设计，仅在加载层追加，保持 rules.json 原文件不变。
_SUPPLEMENTAL_EDUCATION_RULES: List[PatternRule] = [
    PatternRule(
        category="industry-education",
        group_name="教育培训",
        law="《广告法》第二十四条",
        severity="block",
        type="keyword",
        value="提分",
        suggestion="不得承诺提分效果，改为「辅助学习/巩固基础」等客观表述",
    ),
    PatternRule(
        category="industry-education",
        group_name="教育培训",
        law="《广告法》第二十四条",
        severity="block",
        type="keyword",
        value="提分率",
        suggestion="不得承诺提分率，改为客观描述教学服务内容",
    ),
    PatternRule(
        category="industry-education",
        group_name="教育培训",
        law="《广告法》第二十四条",
        severity="block",
        type="keyword",
        value="保送名校",
        suggestion="不得承诺保送结果",
    ),
]


def load_rules(path: str | None = None) -> List[PatternRule]:
    """加载并扁平化全部规则。

    Args:
        path: rules.json 路径；默认指向仓库内 ``docs/marketing/design/rules.json``。

    Returns:
        扁平规则列表，每条含 category/group_name/law/severity/type/value/suggestion。
        末尾追加平台教育行业补充规则（见 ``_SUPPLEMENTAL_EDUCATION_RULES``）。

    Raises:
        FileNotFoundError: 规则文件不存在。
        json.JSONDecodeError: 规则文件非合法 JSON。
    """
    real_path = path or _DEFAULT_RULES_PATH
    with open(real_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    rules: List[PatternRule] = []
    for group in data.get("rule_groups", []):
        category = group.get("id", "")
        group_name = group.get("name", "")
        law = group.get("law", "")
        severity = group.get("severity", "block")
        for pat in group.get("patterns", []):
            rules.append(
                PatternRule(
                    category=category,
                    group_name=group_name,
                    law=law,
                    severity=severity,
                    type=pat.get("type", "keyword"),
                    value=pat.get("value", ""),
                    suggestion=pat.get("suggestion", ""),
                )
            )
    # 追加平台教育行业补充规则（去重：若 rules.json 已含同 value 则跳过）。
    existing_values = {r["value"] for r in rules}
    for sup in _SUPPLEMENTAL_EDUCATION_RULES:
        if sup["value"] not in existing_values:
            rules.append(sup)
    return rules


def load_rules_grouped(path: str | None = None) -> Dict[str, List[PatternRule]]:
    """按 category（规则组 id）分组返回规则。

    Args:
        path: rules.json 路径；默认同 ``load_rules``。

    Returns:
        ``{category: [PatternRule, ...]}`` 字典。
    """
    rules = load_rules(path)
    grouped: Dict[str, List[PatternRule]] = defaultdict(list)
    for r in rules:
        grouped[r["category"]].append(r)
    return dict(grouped)


if __name__ == "__main__":
    # 自检：打印规则数与分组数。
    all_rules = load_rules()
    grouped = load_rules_grouped()
    print(f"共 {len(all_rules)} 条规则，{len(grouped)} 个分组。")
    for cat, lst in sorted(grouped.items()):
        print(f"  {cat}: {len(lst)} 条")
