"""合规审核统一 CLI 入口。

串联 L1 → L2 → L3，对一条文案输出 verdict + 命中详情 + 统计。

用法::

    python compliance/check.py "文案"            # 命令行传入文案
    python compliance/check.py --file x.md       # 从文件读
    python compliance/check.py -j "文案"         # 输出 JSON

判定规则：
    - 任一 L1/L2 命中 final_severity=block → verdict=block
    - 否则有 warn 命中（含 L3 全 warn）→ verdict=warn
    - 否则 → pass
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from typing import List, Optional

from .rules_loader import load_rules
from .l1_keyword import run_l1, L1Hit
from .l2_context import run_l2, L2Result
from .l3_agent import run_l3, L3Risk


def _ensure_utf8_stdout() -> None:
    """强制 stdout 用 UTF-8 输出，避免 Windows GBK 控制台无法打印 emoji。"""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            return
        except Exception:
            pass
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )


class Verdict:
    """单次审核的最终裁定结果。

    Attributes:
        verdict: "block" | "warn" | "pass"
        hits: L1+L2 命中详情（已降级）。
        risks: L3 隐含风险列表。
        stats: 统计字典。
    """

    def __init__(self, verdict: str, hits: List[L2Result],
                 risks: List[L3Risk], stats: dict) -> None:
        self.verdict = verdict
        self.hits = hits
        self.risks = risks
        self.stats = stats

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "stats": self.stats,
            "hits": [h.to_dict() for h in self.hits],
            "risks": [r.to_dict() for r in self.risks],
        }


def _prepare_publication_text(text: str) -> str:
    """从 markdown 文件中提取真实发布正文，跳过 frontmatter 和 prompt 模板。

    ``--no-call`` 预览文件（mode: no-call）包含给 LLM 的完整指令，
    其中的"禁词清单"示例（如「禁'最/第一/提分/保过'」）会触发假阳性，
    因此遇到预览文件返回空字符串。
    """
    # --no-call 预览标记
    if "mode: no-call" in text or 'mode: "no-call"' in text:
        return ""
    # 有 frontmatter 时去掉它
    body = text
    if body.lstrip().startswith("---"):
        # 找到第二个 ---
        parts = body.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
    # 有 ## 📝 正文标记时提取正文（质量门同款格式）
    if "## 📝 正文" in body:
        body = body.split("## 📝 正文", 1)[-1]
    # 去掉发布信息/合规自查等尾部章节
    for marker in ("## 🔍 合规自查", "## 📱 评论区自留", "## 📋 发布信息",
                   "## 📷 拍摄清单", "## ⏰ 定时发布"):
        body = body.split(marker, 1)[0]
    return body.strip()


def check_text(text: str, rules=None) -> Verdict:
    """对文案执行 L1→L2→L3 三级审核，返回 :class:`Verdict`。

    ``text`` 应为已提取的发布正文（不含 frontmatter / prompt 模板）。
    从文件扫描时，调用方应先用 ``_prepare_publication_text`` 提取。
    """
    if rules is None:
        rules = load_rules()

    # L1
    l1_hits: List[L1Hit] = run_l1(text, rules)

    # L2 对 L1 命中做语境降级
    l2_results: List[L2Result] = run_l2(text, l1_hits)

    # L3 隐含风险
    l3_risks: List[L3Risk] = run_l3(text)

    # 判定 verdict
    block_count = sum(1 for r in l2_results if r.final_severity == "block")
    warn_count = sum(1 for r in l2_results if r.final_severity == "warn")
    l3_count = len(l3_risks)

    if block_count > 0:
        verdict = "block"
    elif warn_count > 0 or l3_count > 0:
        verdict = "warn"
    else:
        verdict = "pass"

    stats = {
        "total_rules": len(rules),
        "l1_hits": len(l1_hits),
        "l2_downgraded": sum(1 for r in l2_results if r.downgraded),
        "l2_blocks": block_count,
        "l2_warns": warn_count,
        "l3_risks": l3_count,
    }
    return Verdict(verdict=verdict, hits=l2_results, risks=l3_risks, stats=stats)


# ---- CLI ----

def _format_text_report(v: Verdict) -> str:
    """人类可读的纯文本报告。"""
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append(f"VERDICT: {v.verdict.upper()}")
    lines.append("=" * 60)
    lines.append(f"统计: 规则={v.stats['total_rules']} L1命中={v.stats['l1_hits']} "
                 f"降级={v.stats['l2_downgraded']} block={v.stats['l2_blocks']} "
                 f"warn={v.stats['l2_warns']} L3风险={v.stats['l3_risks']}")
    lines.append("")

    if v.hits:
        lines.append("--- L1/L2 命中 ---")
        for i, h in enumerate(v.hits, 1):
            tag = "BLOCK" if h.final_severity == "block" else "WARN"
            down = " (已降级: " + ",".join(h.reasons) + ")" if h.downgraded else ""
            lines.append(f"[{i}] {tag}{down}")
            lines.append(f"    命中: {h.hit.matched}")
            lines.append(f"    片段: {h.hit.snippet}")
            lines.append(f"    条款: {h.hit.law}")
            lines.append(f"    分类: {h.hit.category}")
            lines.append(f"    建议: {h.hit.suggestion}")
            lines.append("")
    else:
        lines.append("--- L1/L2 无命中 ---")
        lines.append("")

    if v.risks:
        lines.append("--- L3 隐含风险 ---")
        for i, r in enumerate(v.risks, 1):
            lines.append(f"[{i}] {r.kind} (疑似「{r.target}」)")
            lines.append(f"    片段: {r.snippet}")
            lines.append(f"    说明: {r.detail}")
            lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(
        description="营销内容合规审核引擎（L1词库 → L2语境 → L3研判）",
    )
    parser.add_argument("text", nargs="?", help="待审核文案")
    parser.add_argument("--file", "-f", help="从文件读取文案（UTF-8）")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    # 获取文案
    if args.file:
        if not os.path.isfile(args.file):
            print(f"文件不存在: {args.file}", file=sys.stderr)
            return 2
        with open(args.file, "r", encoding="utf-8") as fp:
            text = _prepare_publication_text(fp.read())
        if not text:
            print("[info] 合规闸: 文件为 --no-call 预览模式（含 prompt 模板），跳过自动审核，请在真稿生成后重跑。")
            return 0
    elif args.text is not None:
        text = args.text
    else:
        parser.error("必须提供文案或 --file")

    v = check_text(text)

    if args.json:
        print(json.dumps(v.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_text_report(v))
    # 退出码：block=2 warn=1 pass=0
    return {"block": 2, "warn": 1, "pass": 0}.get(v.verdict, 0)


if __name__ == "__main__":
    sys.exit(main())
