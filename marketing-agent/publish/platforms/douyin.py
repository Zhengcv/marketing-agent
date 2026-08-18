"""抖音发布表单实现。

依赖 AbstractBrowserEngine 接口（Lane A）完成浏览器操作。
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class DyPost:
    """抖音发布内容。"""
    title: str  # 视频描述（≤55字）
    video_path: Path  # 视频文件路径
    cover_path: Optional[Path] = None  # 封面图路径
    topics: List[str] = field(default_factory=list)  # 话题标签（≤5个）
    schedule_time: Optional[str] = None  # 定时发布时间
    location: Optional[str] = None  # 地点


class DyPublisher:
    """抖音发布器。需注入 AbstractBrowserEngine 实例。"""

    def __init__(self, engine):
        self.engine = engine
        self._filled = False

    def fill_form(self, post: DyPost) -> dict:
        """将 DyPost 内容填入抖音发布表单。
        返回发布前的预览摘要 dict。
        """
        errors = self.validate(post)
        if errors:
            raise ValueError("；".join(errors))

        self.engine.navigate("https://creator.douyin.com/creator-micro/content/upload")
        fields = {
            "title": post.title,
            "video_path": str(post.video_path),
            "topics": ",".join(post.topics),
        }
        if post.cover_path:
            fields["cover_path"] = str(post.cover_path)
        if post.schedule_time:
            fields["schedule_time"] = post.schedule_time
        if post.location:
            fields["location"] = post.location
        self.engine.fill_form(fields)
        self._filled = True
        return self._build_preview(post)

    def publish(self) -> None:
        """点击「发布」按钮。"""
        if not self._filled:
            raise RuntimeError("必须先调用 fill_form() 再发布")
        self.engine.click("#publish-btn")

    def validate(self, post: DyPost) -> List[str]:
        """校验发布内容。返回违规列表，空列表=通过。"""
        errors = []
        if not post.title.strip():
            errors.append("标题不能为空")
        elif len(post.title) > 55:
            errors.append("标题不能超过55字")
        if post.video_path is None or not str(post.video_path).strip():
            errors.append("视频文件路径不能为空")
        if len(post.topics) > 5:
            errors.append("话题不能超过5个")
        return errors

    @staticmethod
    def _build_preview(post: DyPost) -> dict:
        """构建预览摘要。"""
        title_summary = post.title[:55] + "..." if len(post.title) > 55 else post.title
        return {
            "platform": "douyin",
            "title": title_summary,
            "video_path": str(post.video_path),
            "cover_path": str(post.cover_path) if post.cover_path else None,
            "topics": list(post.topics),
            "schedule_time": post.schedule_time,
            "location": post.location,
        }