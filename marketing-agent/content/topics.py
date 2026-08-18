"""选题库：内置家教平台选题清单。

每个选题包含：标题、平台、类型、合规自查通过标记。
选题来源：docs/marketing/playbooks/S2-social-media-redbook-douyin.md 的选题库与内容日历。

用法（CLI）：
    python topics.py                 # 列出全部选题
    python topics.py --platform xhs   # 只列小红书选题
    python topics.py --platform dy    # 只列抖音选题
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

# 平台常量
PLATFORM_XHS = "xiaohongshu"  # 小红书
PLATFORM_DY = "douyin"        # 抖音
PLATFORM_BOTH = "both"        # 两平台通用


@dataclass(frozen=True)
class Topic:
    """一条选题。

    title        标题（发布时可调整）
    platform     所属平台：xiaohongshu / douyin / both
    content_type 内容类型：干货清单 / 避坑指南 / 认证科普 / 故事案例 / 互动提问
    compliant    合规自查是否已通过（True = 已对照 S2 合规红线逐条打过勾）
    note         选题说明 / 写作用提示（可选）
    """

    title: str
    platform: str
    content_type: str
    compliant: bool = False
    note: str = ""


# 内置选题池（10 条）。内容类型与标题参考 playbook 的选题库：
# "怎么判断家教老师靠不靠谱" "L2学历认证和L3教资认证区别" "试课家长该观察什么" 等
TOPIC_POOL: List[Topic] = [
    Topic(
        title="怎么判断家教老师靠不靠谱？看这 4 个细节",
        platform=PLATFORM_XHS,
        content_type="干货清单",
        compliant=True,
        note="家长视角，4 项自查清单，避开'师资力量强'式空话",
    ),
    Topic(
        title="L2 学历认证和 L3 教资认证，到底有什么区别？",
        platform=PLATFORM_BOTH,
        content_type="认证科普",
        compliant=True,
        note="教育市场类内容，适合周六发；解释 L1/L2/L3 三档认证",
    ),
    Topic(
        title="试课的时候，家长到底该观察什么？",
        platform=PLATFORM_BOTH,
        content_type="干货清单",
        compliant=True,
        note="核心观点：观察孩子是否愿意参与，而非老师讲得精不精彩",
    ),
    Topic(
        title="给家教付钱之前，先把这 3 个问题问清楚",
        platform=PLATFORM_XHS,
        content_type="避坑指南",
        compliant=True,
        note="信息费谁付/能不能退/有没有平台介入，正好落在平台强项",
    ),
    Topic(
        title="找家教 3 个坑，你踩过几个？",
        platform=PLATFORM_DY,
        content_type="避坑指南",
        compliant=True,
        note="抖音 45 秒口播：只看价格/只看试讲效果/没搞清信息费",
    ),
    Topic(
        title="一位妈妈从被骗到找到靠谱老师的经历",
        platform=PLATFORM_XHS,
        content_type="故事案例",
        compliant=True,
        note="情感共鸣型；不指名不道姓，不展示成绩单",
    ),
    Topic(
        title="老师说自己'经验丰富'，该怎么验证？",
        platform=PLATFORM_BOTH,
        content_type="干货清单",
        compliant=True,
        note="落到可执行动作：查认证、看证件、约试讲观察反应",
    ),
    Topic(
        title="给孩子找家教前，家长必问的 5 个问题（已核对为 4+2 结构）",
        platform=PLATFORM_XHS,
        content_type="干货清单",
        compliant=True,
        note="复用 redbook-01 范文选题；注意正文章节用 4 或 6 项，避开 AI 味的恰好 5 项",
    ),
    Topic(
        title="信息费该谁付？家长还是老师？",
        platform=PLATFORM_BOTH,
        content_type="认证科普",
        compliant=True,
        note="直接落在平台定位：信息费老师单边付，家长只付课时费",
    ),
    Topic(
        title="家里孩子不想补课，还找家教吗？",
        platform=PLATFORM_DY,
        content_type="互动提问",
        compliant=True,
        note="互动型选题，引导家长评论区分享，不做任何承诺",
    ),
]


def list_topics(platform: Optional[str] = None) -> List[Topic]:
    """按平台过滤选题列表。

    platform 为 None 返回全部；否则只返回该平台或 'both' 的选题。
    """
    if platform is None:
        return list(TOPIC_POOL)
    return [t for t in TOPIC_POOL if t.platform in (platform, PLATFORM_BOTH)]


def summary(topic: Topic, idx: int) -> str:
    """一行摘要，用于 CLI 展示（用 ASCII 标记，避免 Windows GBK 编码问题）。"""
    flag = "[合规OK]" if topic.compliant else "[未过合规自查]"
    return f"[{idx}] {topic.title} ({topic.platform}/{topic.content_type}) {flag}"


def main() -> None:
    """CLI 入口：列出全部或按平台过滤的选题。"""
    import argparse

    parser = argparse.ArgumentParser(description="Tutor-Match 营销选题库")
    parser.add_argument(
        "--platform",
        choices=[PLATFORM_XHS, PLATFORM_DY],
        default=None,
        help="只列某平台选题（both 的选题两平台都列出）",
    )
    args = parser.parse_args()

    topics = list_topics(args.platform)
    print(f"共 {len(topics)} 条选题：")
    for idx, t in enumerate(topics):
        print("  " + summary(t, idx))
    print("\n提示：选题发布前用 quality/check.py 过一遍质量门。")


if __name__ == "__main__":
    main()
