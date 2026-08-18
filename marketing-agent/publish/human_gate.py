"""人工确认闸。

半自动发布流程的最后一道防线：
    1. generate_preview() 生成预览摘要
    2. request_confirm() 等待人工输入
    3. 按 decision 执行
"""

from dataclasses import dataclass
from typing import Optional, Callable, Dict
from enum import Enum


class GateDecision(Enum):
    CONFIRM = "confirm"  # 人工确认发布
    ABORT = "abort"  # 取消发布
    EDIT = "edit"  # 返回编辑


@dataclass
class GateResult:
    decision: GateDecision
    reason: str = ""
    edited_fields: Optional[Dict] = None


class HumanGate:
    """人工确认闸。半自动发布流程的最后一道防线。

    流程：
    1. generate_preview() -> 生成预览摘要
    2. request_confirm() -> 等待人工输入
    3. 按 decision 执行：CONFIRM -> 发布 / ABORT -> 取消 / EDIT -> 返回编辑
    """

    def __init__(self, input_fn: Optional[Callable[[str], str]] = None):
        """input_fn: 获取用户输入的回调函数。用于测试注入。
        None 时使用内置 input()。
        """
        self._input_fn = input_fn

    def generate_preview(self, platform: str, post_summary: dict) -> str:
        """生成发布预览文本。包含平台/标题/正文摘要/标签/图数/定时/合规状态。"""
        lines = []
        lines.append(f"=== 发布预览 ===")
        lines.append(f"平台: {platform}")
        lines.append(f"标题: {post_summary.get('title', '')}")
        if "body_summary" in post_summary:
            lines.append(f"正文摘要: {post_summary.get('body_summary', '')}")
        if "tags" in post_summary:
            tags = post_summary.get("tags", [])
            lines.append(f"标签: {', '.join(tags) if tags else '无'}")
        if "image_count" in post_summary:
            lines.append(f"图片数量: {post_summary.get('image_count', 0)}")
        if "video_path" in post_summary:
            lines.append(f"视频文件: {post_summary.get('video_path', '')}")
        if "topics" in post_summary:
            topics = post_summary.get("topics", [])
            lines.append(f"话题: {', '.join(topics) if topics else '无'}")
        schedule = post_summary.get("schedule_time")
        lines.append(f"定时发布: {schedule if schedule else '立即'}")
        if "location" in post_summary:
            lines.append(f"地点: {post_summary.get('location', '无')}")
        return "\n".join(lines)

    def request_confirm(self, preview: str) -> GateResult:
        """展示预览文本，等待人工输入确认。

        输入: "Y/y/yes" -> CONFIRM, "N/n/no" -> ABORT, "E/e/edit" -> EDIT。
        测试时通过 input_fn 注入模拟输入。
        """
        input_fn = self._input_fn or input
        while True:
            raw = input_fn(preview + "\n\n确认发布? [Y]es / [N]o / [E]dit: ")
            cleaned = raw.strip().lower()
            if cleaned in ("y", "yes"):
                return GateResult(decision=GateDecision.CONFIRM, reason="人工确认发布")
            if cleaned in ("n", "no"):
                return GateResult(decision=GateDecision.ABORT, reason="用户取消发布")
            if cleaned in ("e", "edit"):
                return GateResult(decision=GateDecision.EDIT, reason="用户返回编辑")

    @staticmethod
    def is_auto_publish_disabled() -> bool:
        """纯 API 签名发布禁用检查。始终返回 True（架构红线）。"""
        return True