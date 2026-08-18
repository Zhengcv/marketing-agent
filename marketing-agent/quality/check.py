"""质量门 CLI：读取一份文案并输出 Markdown 评审报告。

用法：
    python quality/check.py --file content.md
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Dict, Iterable, List

# 兼容直接执行 ``python quality/check.py``（此时包父目录不在 sys.path）。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quality.anti_ai import AITrace, detect_ai_traces
from quality.expert_panel import PanelReport, prepare_publication_text, review_content
from quality.seven_sweeps import Issue, run_seven_sweeps


def _escape(value: str) -> str:
    """避免文案中的表格符号破坏 Markdown 表格。"""
    return value.replace("|", "\\|").replace("\n", " ")


def _issue_lines(issues: Iterable[Issue]) -> List[str]:
    lines = []
    for issue in issues:
        lines.append(
            f"- **{_escape(issue.quote)}**：{_escape(issue.problem)} 建议：{_escape(issue.suggestion)}"
        )
    return lines


def _trace_lines(traces: Iterable[AITrace]) -> List[str]:
    lines = []
    for trace in traces:
        lines.append(
            f"- `{trace.category}` **{_escape(trace.quote)}**：{_escape(trace.problem)} "
            f"建议：{_escape(trace.suggestion)}"
        )
    return lines


def render_report(text: str, source: str = "") -> str:
    """串联七遍、反 AI 和专家评审，生成完整 Markdown。"""
    publication_text = prepare_publication_text(text)
    sweeps = run_seven_sweeps(publication_text)
    traces = detect_ai_traces(publication_text)
    panel = review_content(text)
    lines = [
        "# 文案质量门报告",
        "",
        f"- 来源：`{_escape(source or 'stdin')}`",
        f"- 总字数：{len(text)}",
        f"- AI 痕迹：{len(traces)} 条",
        "",
        "## 七遍扫描",
        "",
    ]
    sweep_titles: Dict[str, str] = {
        "clarity": "1. Clarity 清晰度",
        "voice": "2. Voice 品牌一致",
        "so_what": "3. So What 利益连接",
        "prove_it": "4. Prove It 证据支撑",
        "specificity": "5. Specificity 具体化",
        "emotion": "6. Emotion 情感唤起",
        "zero_risk": "7. Zero Risk 零风险",
    }
    for key, title in sweep_titles.items():
        issues = sweeps[key]
        lines.append(f"### {title}（{len(issues)} 条）")
        lines.extend(_issue_lines(issues) or ["- 未发现问题。"])
        lines.append("")
    lines.extend(["## 反 AI 检测", ""])
    lines.extend(_trace_lines(traces) or ["- 未发现列出的 AI 痕迹。"])
    lines.extend(["", "## 专家评审团", "", "| 人设 | 分数 |", "|---|---:|"])
    labels = {
        "conversion_copywriter": "转化文案师（说服力）",
        "target_parent": "目标家长视角（可信度）",
        "compliance_expert": "合规专家（风险）",
    }
    for name, score in panel.scores.items():
        lines.append(f"| {labels[name]} | {score:.1f} |")
    lines.extend([f"| **均值** | **{panel.average:.2f}** |", "", f"**verdict：{panel.verdict}**", ""])
    lines.append("### 低分原因")
    lines.extend([f"- {reason}" for reason in panel.low_score_reasons] or ["- 无。"])
    lines.append("")
    lines.append("### 改进建议")
    lines.extend([f"- {suggestion}" for suggestion in panel.improvement_suggestions])
    lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    """CLI 主函数，返回进程退出码。"""
    parser = argparse.ArgumentParser(description="Tutor-Match 文案质量门")
    parser.add_argument("--file", required=True, help="待检查的 Markdown/文本文件")
    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        parser.error(f"无法读取文件 {path}: {exc}")
    report = render_report(text, str(path))
    # Windows 默认 GBK 控制台无法编码中文引号/emoji；报告契约仍统一输出 UTF-8。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    try:
        print(report)
    except UnicodeEncodeError:
        # 兼容少数不可重配置的 stdout（例如宿主嵌入式解释器）。
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            raise
        buffer.write((report + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
