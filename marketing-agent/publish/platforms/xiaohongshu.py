"""小红书发布表单实现。

依赖 AbstractBrowserEngine 接口（Lane A）完成浏览器操作。
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class XhsPost:
    """小红书发布内容。"""
    title: str  # 标题（≤20字）
    body: str  # 正文
    tags: List[str] = field(default_factory=list)  # 话题标签（≤5个）
    images: List[Path] = field(default_factory=list)  # 图片路径（1-9张）
    schedule_time: Optional[str] = None  # 定时发布时间（ISO 8601），None=立即
    location: Optional[str] = None  # 地点


class XhsPublisher:
    """小红书发布器。需注入 AbstractBrowserEngine 实例。"""

    def __init__(self, engine):
        self.engine = engine
        self._filled = False

    def fill_form(self, post: XhsPost) -> dict:
        """将 XhsPost 内容填入小红书发布表单。
        返回发布前的预览摘要 dict（标题/正文摘要/标签/图数/定时）。
        """
        errors = self.validate(post)
        if errors:
            raise ValueError("；".join(errors))

        self.engine.navigate("https://www.xiaohongshu.com/publish")
        self.engine.fill_form({
            "title": post.title,
            "body": post.body,
            "tags": ",".join(post.tags),
            "images": [str(p) for p in post.images],
            "location": post.location or "",
            "schedule_time": post.schedule_time or "",
        })
        self._filled = True
        return self._build_preview(post)

    def publish(self) -> None:
        """点击「发布」按钮。调用前必须先 fill_form()。"""
        if not self._filled:
            raise RuntimeError("必须先调用 fill_form() 再发布")
        self.engine.click("#publish-btn")

    def validate(self, post: XhsPost) -> List[str]:
        """校验发布内容。返回违规列表，空列表=通过。"""
        errors = []
        if not post.title.strip():
            errors.append("标题不能为空")
        elif len(post.title) > 20:
            errors.append("标题不能超过20字")
        if not post.body.strip():
            errors.append("正文不能为空")
        if len(post.tags) > 5:
            errors.append("标签不能超过5个")
        if len(post.images) < 1:
            errors.append("至少需要1张图片")
        if len(post.images) > 9:
            errors.append("图片不能超过9张")
        return errors

    @staticmethod
    def _build_preview(post: XhsPost) -> dict:
        """构建预览摘要。"""
        body_summary = post.body[:50] + "..." if len(post.body) > 50 else post.body
        return {
            "platform": "xiaohongshu",
            "title": post.title,
            "body_summary": body_summary,
            "tags": list(post.tags),
            "image_count": len(post.images),
            "schedule_time": post.schedule_time,
            "location": post.location,
        }