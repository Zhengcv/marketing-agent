"""Tutor-Match 发布通道层 (积木④)。

半自动发布通道：填入表单 → 预览 → 人工确认 → 发布。

平台支持：
    - 小红书 (xiaohongshu)
    - 抖音 (douyin)

依赖：
    - browser/engine.py 的 AbstractBrowserEngine / UnittestEngine 接口（Lane A）
    - publish 本身不依赖真实浏览器，所有测试使用 UnittestEngine。
"""

from .human_gate import HumanGate, GateDecision, GateResult

__all__ = [
    "HumanGate",
    "GateDecision",
    "GateResult",
]