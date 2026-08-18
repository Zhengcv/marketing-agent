#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 内容生成器 CLI（小红书 / 抖音图文笔记与口播脚本）。

功能：
    1. 读取 content/prompts/<platform>.md 模板，填入话题后作为 user 消息发给 LLM；
    2. 调 OpenAI-compatible Chat Completions 接口（POST {base_url}/chat/completions）；
    3. 输出带 YAML frontmatter 的 markdown 文件，并打印质量/合规自查提示。

用法示例（在 marketing-agent/ 下执行）：
    python content/generate.py --platform xiaohongshu --topic "怎么找靠谱家教" --output out/xhs-01.md
    python content/generate.py --platform douyin --topic "找家教避坑" --output out/douyin-01.md
    python content/generate.py --topic-id 0 --platform xiaohongshu --output out/xhs-02.md
    python content/generate.py --list-topics                    # 列出选题库
    python content/generate.py --platform douyin --topic "测试" --no-call --output preview.md

依赖：
    # 依赖: pip install requests
    优先使用 requests 库；未安装时自动回退到标准库 urllib（会打印说明）。

设计约定：
    - 模板里的铁律段落（角色设定 / 反 AI 化 / 合规红线 / 输出格式）原样保留，
      只替换主题占位符（兼容 `**[主题]**`、`[主题]`、`{topic}` 三种写法）。
    - LLM 错误分类：4xx → 提示检查 API key/参数；5xx/网络 → 提示重试。
    - 话题命中违规词时：生成前置警告，并在 frontmatter 里标注需合规复核。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 让脚本 / 测试都能定位同目录的 topics.py（Windows 下 run 的 cwd 可能不同）
BASE_DIR = Path(__file__).resolve().parent
PROMPT_DIR = BASE_DIR / "prompts"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from topics import (  # noqa: E402
    PLATFORM_BOTH,
    PLATFORM_DY,
    PLATFORM_XHS,
    TOPIC_POOL,
    Topic,
    list_topics,
    summary,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_TEMPERATURE = 0.8
HTTP_CONNECT_TIMEOUT = 15  # 建立连接超时（秒）
HTTP_READ_TIMEOUT = 120    # 读取响应超时（秒）

# 平台 → prompt 模板文件（相对 PROMPT_DIR，即 content/prompts/ 目录）
PLATFORM_TEMPLATES = {
    PLATFORM_XHS: "xiaohongshu.md",
    PLATFORM_DY: "douyin.md",
}

# 系统提示：约束模型只产出成品，不解释、不删模板铁律
SYSTEM_PROMPT = (
    "你是一名资深中文内容创作者，熟悉本地家教中介行业的话术与合规红线。"
    "请严格依据用户提供的写作模板（含角色设定、结构铁律、反AI化铁律、合规红线、输出格式）"
    "生成内容。必须遵守模板中所有铁律与合规红线，直接输出最终成品："
    "不要输出任何解释、前言提醒，不要用 Markdown 代码块包裹正文。"
)

# 内置疑似违规词（来自两块模板「合规红线」的禁词；rules.json 会追加）
_VIOLATION_BASE: Tuple[str, ...] = (
    "提分", "保过", "包过", "稳过", "升学率", "名师", "免费试课", "培训机构",
    "唯一", "第一", "最好", "最佳", "最低价", "最便宜", "国家级", "最高级",
    "加微信", "微信号", "加我微信", "保证提分", "承诺提分", "签约包过",
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _fix_stdout() -> None:
    """Windows 控制台默认 GBK，打印 emoji（如 ⚠️）可能抛 UnicodeEncodeError；尽量切到 utf-8。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            pass  # 个别环境下不可重配，忽略即可


def _yaml_scalar(value: Any) -> str:
    """把任意值转为安全的 YAML 标量（含特殊字符时自动加双引号）。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    # 待 YAML 解析的歧义值：空串 / 首尾空白 / 数字 / 布尔 / 特殊字符
    if text.strip() != text or text == "":
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if re.fullmatch(r"-?\d+(\.\d+)?", text) is not None:
        return '"' + text + '"'
    if text.lower() in ("true", "false", "null", "~", "yes", "no", "on", "off"):
        return '"' + text + '"'
    if any(ch in text for ch in ':#{}[],&*!|>%@`'):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def build_frontmatter(meta: Dict[str, Any]) -> str:
    """把元信息渲染成 YAML frontmatter 文本（--- 包裹）。"""
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt 组装
# ---------------------------------------------------------------------------

def load_template(platform: str) -> str:
    """读取指定平台的 prompt 模板内容（整段铁律保留，便于 LLM 遵守）。"""
    rel = PLATFORM_TEMPLATES.get(platform)
    if rel is None:
        raise ValueError(f"未知平台: {platform}（可选: {list(PLATFORM_TEMPLATES)}）")
    path = PROMPT_DIR / Path(rel).name  # 只用文件名，PROMPT_DIR 已定位 prompts/ 目录
    if not path.is_file():
        raise FileNotFoundError(f"找不到 prompt 模板: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"prompt 模板为空: {path}")
    return text


def fill_topic(template: str, topic: str) -> str:
    """把模板里的主题占位符替换成实际话题。

    兼容三种写：`**[主题]**`（两块模板实际用法）、`[主题]`、
    `{topic}`（需求方习惯写法）。其余铁律段落原样不动。
    """
    prompt = template.replace("**[主题]**", "**" + topic + "**")
    prompt = prompt.replace("[主题]", topic)
    prompt = prompt.replace("{topic}", topic)
    return prompt


# ---------------------------------------------------------------------------
# 违规词检查（话题预检，做不了正式合规，但能前置警告）
# ---------------------------------------------------------------------------

_violation_word_cache: Optional[Tuple[str, ...]] = None


def load_violation_words() -> Tuple[str, ...]:
    """合并内置禁词 + docs/marketing/design/rules.json 的 keyword 词元（去重）。

    只取 rules.json 里 type=keyword 的短词条（2~10 字、无正则元字符），
    长规则 / 正则规则交给 compliance/check.py 做正式检查。
    """
    global _violation_word_cache
    if _violation_word_cache is not None:
        return _violation_word_cache

    words: List[str] = list(_VIOLATION_BASE)
    rules_path = BASE_DIR.parent.parent / "docs" / "design" / "rules.json"
    try:
        if not rules_path.is_file():
            raise FileNotFoundError(str(rules_path))  # 走到 except 打印一条 warn
        data = json.loads(rules_path.read_text(encoding="utf-8"))
        for group in data.get("rule_groups", []):
            for pat in group.get("patterns", []):
                if pat.get("type") != "keyword":
                    continue
                word = pat.get("value")
                if not isinstance(word, str):
                    continue
                word = word.strip()
                if not (2 <= len(word) <= 10):
                    continue
                if any(ch in word for ch in ".*+?^$[](){}|\\/"):
                    continue  # 跳过带正则元字符的条目，误判率太高
                words.append(word)
    except (OSError, ValueError, TypeError) as exc:
        print(f"[warn] 读取合规规则库失败，仅用内置禁词预检：{exc}")

    seen: set = set()  # 去重，保持首次出现顺序
    unique: List[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    _violation_word_cache = tuple(unique)
    return _violation_word_cache


def find_violation_words(topic: str) -> List[str]:
    """返回话题里命中的疑似违规词；没有则返回空列表。"""
    lower = topic.lower()
    return [w for w in load_violation_words() if w in lower]


# ---------------------------------------------------------------------------
# LLM 调用（OpenAI-compatible chat completions）
# ---------------------------------------------------------------------------

class LlmCallError(Exception):
    """LLM 调用失败。kind: 4xx / 5xx / network / config / parse。"""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


# LLM 错误分类 → 给用户的一句行动建议
_KIND_TIP = {
    "4xx": "请检查 DEEPSEEK_API_KEY / --api-key，以及 --model、--base-url 是否配置正确。",
    "5xx": "服务端或网络异常，可稍后重试。",
    "network": "网络问题，请检查网络连接与 --base-url。",
    "config": "配置问题，请检查命令行参数。",
    "parse": "响应解析失败，请检查 --model 是否受支持。",
}


def _strip_code_fence(content: str) -> str:
    """容忍 LLM 用 ``` 包裹正文：去掉首尾代码围栏。"""
    content = content.strip()
    lines = content.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_content(data: Any) -> str:
    """从响应中提取正文，兼容 markdown/JSON 两种返回形态。"""
    if isinstance(data, str):
        # 极少数兼容网关直接把正文当纯文本返回
        return _strip_code_fence(data)
    try:
        choices = data["choices"]
        first = choices[0]
        message = first.get("message") or {}
        content = message.get("content") or first.get("text") or ""
        if isinstance(content, list):
            # 部分实现返回 [{type: text, text: ...}] 的分块数组
            content = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") in (None, "text", "output_text")
            )
        if content:
            return _strip_code_fence(str(content))
    except (KeyError, TypeError, IndexError, AttributeError):
        pass
    raise LlmCallError(
        "parse",
        "无法从 LLM 响应中解析出正文（content 字段缺失）。可能是 --model 名称不支持或网关返回异常"
        f"；原始响应（前 200 字符）：{str(data)[:200]!r}",
    )


def _peek_response_text(text: str) -> str:
    """截取错误响应正文用于提示（避免超长刷屏）。"""
    return (text or "").strip()[:500]


def _raise_for_http(status: int, detail: str) -> None:
    """按 HTTP 状态码分类抛错，给用户可执行的排查建议。"""
    detail_suffix = f" 后端响应：{detail}" if detail else ""
    if 400 <= status < 500:
        raise LlmCallError(
            "4xx",
            f"HTTP {status}（请求被拒，通常因 API key 无效或参数错误）："
            f"请检查 DEEPSEEK_API_KEY / --api-key、--model、--base-url。{detail_suffix}",
        )
    raise LlmCallError(
        "5xx",
        f"HTTP {status}（服务端或网络异常）：请稍后重试；持续失败请检查 --base-url 服务状态。{detail_suffix}",
    )


def _payload(model: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """组装 Chat Completions 请求体（temperature 固定 0.8）。"""
    return {
        "model": model,
        "messages": messages,
        "temperature": DEFAULT_TEMPERATURE,
    }


def _call_requests(base_url: str, api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    """用 requests 调接口（缺依赖时会抛 ImportError，由调度者决定回退）。"""
    import requests

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            url,
            json=_payload(model, messages),
            headers=headers,
            timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
        )
    except requests.exceptions.Timeout as exc:
        raise LlmCallError(
            "network",
            f"请求超时（connect {HTTP_CONNECT_TIMEOUT}s / read {HTTP_READ_TIMEOUT}s）："
            f"请检查网络，可稍后重试。{exc}",
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise LlmCallError(
            "network",
            f"网络错误：无法连接 {url}。请检查网络与 --base-url。{exc}",
        ) from exc

    if resp.status_code >= 400:
        _raise_for_http(resp.status_code, _peek_response_text(resp.text))
    try:
        data = resp.json()
    except ValueError as exc:
        raise LlmCallError("parse", f"响应不是合法 JSON：{resp.text[:200]!r}") from exc
    return _extract_content(data)


def _call_urllib(base_url: str, api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    """纯标准库 urllib 实现同一请求（requests 不可用时的兜底）。"""
    import urllib.error
    import urllib.request

    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(_payload(model, messages), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_READ_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        _raise_for_http(exc.code, detail)
        return ""  # 不可达（_raise_for_http 必抛）
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise LlmCallError(
            "network",
            f"网络错误/超时：无法连接 {url}。请检查网络与 --base-url，可稍后重试。{reason}",
        ) from exc

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise LlmCallError("parse", f"响应不是合法 JSON：{raw[:200]!r}") from exc
    return _extract_content(data)


_requests_available_cache: Optional[bool] = None


def _requests_available() -> bool:
    """探测 requests 是否可用（结果缓存，只探测一次）。"""
    global _requests_available_cache
    if _requests_available_cache is None:
        try:
            import requests  # noqa: F401

            _requests_available_cache = True
        except ImportError:
            _requests_available_cache = False
    return _requests_available_cache


def call_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
) -> str:
    """调用 OpenAI 兼容 Chat Completions 并返回正文。

    优先 requests；未安装时回退 urllib，并打印说明（保证至少一条可用路径）。
    """
    if not api_key.strip():
        raise LlmCallError("config", "缺少 API key：设置环境变量 DEEPSEEK_API_KEY 或使用 --api-key 传入。")
    if _requests_available():
        print("[info] HTTP 客户端：requests")
        return _call_requests(base_url, api_key, model, messages)
    print("[info] 未安装 requests（pip install requests 可获得更好的重试策略）；已回退到标准库 urllib。")
    return _call_urllib(base_url, api_key, model, messages)


# ---------------------------------------------------------------------------
# 选题库 / 话题解析
# ---------------------------------------------------------------------------

def resolve_topic(topic: Optional[str], topic_id: Optional[int]) -> Tuple[str, Optional[Topic]]:
    """把 --topic 或 --topic-id 解析成最终话题文本，返回 (话题, 选题对象或 None)。"""
    if topic is not None:
        return topic, None
    if topic_id is None:
        raise ValueError("缺少 --topic 或 --topic-id")  # parse 已拦，这里兜底
    total = len(TOPIC_POOL)
    if not (0 <= topic_id < total):
        raise ValueError(f"--topic-id {topic_id} 超出范围（0~{total - 1}），先跑 --list-topics 查看编号")
    picked = TOPIC_POOL[topic_id]
    return picked.title, picked


def list_topics_table(platform: Optional[str] = None) -> List[str]:
    """生成选题清单展示行。编号统一为全库下标（即 --topic-id 的取值）。"""
    topics = list_topics(platform)
    lines = [f"共 {len(topics)} 条选题（编号对应 --topic-id，从 0 开始）："]
    for t in topics:
        idx = TOPIC_POOL.index(t)  # 全库下标，保证与 --topic-id 一致
        lines.append("  " + summary(t, idx))
    lines.append("")
    lines.append("提示：可执行 python content/generate.py --topic-id <编号> --platform <平台> --output out/x.md 生成内容；")
    lines.append("      选题发布前用 python quality/check.py 过一遍质量门。")
    return lines


def _default_output_path(platform: str, topic: str) -> str:
    """未传 --output 时生成默认输出路径：out/<platform>-<话题>-<时间>.md"""
    slug = re.sub(r"[^\w一-鿿-]+", "-", topic).strip("-")[:20] or "topic"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return str(Path("out") / f"{platform}-{slug}-{ts}.md")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def generate_with_args(args: argparse.Namespace) -> Path:
    """执行一次生成（参数已通过 parse_args 校验），返回输出文件路径。"""
    platform = args.platform
    topic, topic_obj = resolve_topic(args.topic, args.topic_id)

    # 选题平台不匹配时给警告，但不阻断（用户可能故意跨平台复用）
    if topic_obj is not None and platform not in (topic_obj.platform, PLATFORM_BOTH):
        print(f"[warn] 选题「{topic_obj.title}」建议平台为 {topic_obj.platform}，与 --platform {platform} 不一致，已继续。")

    # 1. 组装 prompt
    template = load_template(platform)
    prompt = fill_topic(template, topic)

    # 2. 话题违规词预检（正式检查靠 compliance/check.py）
    hits = find_violation_words(topic)
    needs_check = bool(hits)
    if hits:
        print("[!] 话题含疑似违规词：" + "、".join(sorted(set(hits))))
        print("    请改写话题并确保不违反模板合规红线；本次生成的产物务必跑 compliance/check.py 复核。")

    # 3. frontmatter 元信息
    now = datetime.now()
    meta = {
        "platform": platform,
        "topic": topic,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "mode": "no-call" if args.no_call else "live",
        "compliance": (
            "warn：话题含疑似违规词，需人工改写并跑 compliance/check.py 复核"
            if needs_check
            else "话题初检通过；建议生成后跑 compliance/check.py 做正式合规检查"
        ),
    }

    # 4. 生成正文（no-call 只输出 prompt 预览，便于无 key 自测与人工审 prompt）
    if args.no_call:
        body = (
            "<!-- 以下为组装好的 prompt 预览（--no-call 模式，未调用 LLM）。\n"
            "     整段内容即发给模型的 user 消息；可直接粘贴到模型对话中生成。 -->\n\n"
            + prompt
        )
    else:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        content = call_chat_completion(args.base_url, args.api_key, args.model, messages)
        if not content.strip():
            raise LlmCallError("parse", "LLM 返回了空正文，请重试或检查 --model。")
        body = content

    # 5. 写文件（自动创建目录）
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = build_frontmatter(meta) + "\n\n" + body.rstrip() + "\n"
    output.write_text(rendered, encoding="utf-8")
    return output


def print_hint(output: Path) -> None:
    """生成完成后的收尾提示（质量门 / 合规门）。"""
    print()
    print(f"生成完成 → {output.resolve()}")
    print(f"⚠️ 建议跑 python quality/check.py --file {output} 和 python compliance/check.py --file {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Tutor-Match AI 内容生成器（小红书/抖音）。从 prompts/<platform>.md 模板 + 话题 → 调 LLM 出稿。",
        epilog="示例：python content/generate.py --platform xiaohongshu "
               "--topic \"怎么找靠谱家教\" --output out/xhs-01.md",
    )
    parser.add_argument(
        "--platform",
        choices=[PLATFORM_XHS, PLATFORM_DY],
        default=None,
        help="内容平台（生成模式下必填）：xiaohongshu | douyin",
    )
    parser.add_argument("--topic", default=None, help="话题文本（与 --topic-id 二选一）")
    parser.add_argument(
        "--topic-id",
        type=int,
        default=None,
        help="选题库编号（从 0 开始，用 --list-topics 查看；与 --topic 二选一）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出文件路径（默认 out/<platform>-<话题>-<时间>.md，目录自动创建）",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LLM 模型名（默认 {DEFAULT_MODEL}）")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"OpenAI 兼容接口地址（默认 {DEFAULT_BASE_URL}）",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key（默认读环境变量 DEEPSEEK_API_KEY）",
    )
    parser.add_argument(
        "--no-call",
        action="store_true",
        help="不调用 LLM，只把组装好的 prompt 拼进输出文件（无 key 自测用）",
    )
    parser.add_argument(
        "--list-topics",
        action="store_true",
        help="列出选题库后退出（--platform 可作过滤；编号始终是全库编号）",
    )
    return parser


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """解析参数并做业务校验（参数缺失时打印 usage 并以 exit 2 退出）。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_topics:
        if args.topic is not None or args.topic_id is not None or args.output is not None:
            parser.error("--list-topics 与 --topic / --topic-id / --output 不能同时使用")
        return args

    if args.platform is None:
        parser.error("请用 --platform 指定平台：xiaohongshu | douyin（或在 --list-topics 模式下查看选题）")
    if args.topic is not None and args.topic_id is not None:
        parser.error("--topic 与 --topic-id 只能二选一")
    if args.topic is None and args.topic_id is None:
        parser.error("缺少话题：请用 --topic 传话题文本，或用 --topic-id 从选题库选择（--list-topics 查看编号）")
    if args.topic is not None and not args.topic.strip():
        parser.error("话题不能为空字符串")
    return args


def main() -> int:
    """CLI 入口。返回退出码（0 正常，1 出错）。"""
    _fix_stdout()  # Windows GBK 控制台兜底
    args = parse_args()

    if args.list_topics:
        print("\n".join(list_topics_table(args.platform)))
        return 0

    try:
        # 缺 API key 的校验放在生成前，用 parse 级别的 usage 报错更友好
        api_key = (args.api_key or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not args.no_call and not api_key:
            print("[错误] config: 缺少 API key。请设置环境变量 DEEPSEEK_API_KEY，或传 --api-key。")
            print("       调试连不上服务时，可先加 --no-call 只预览 prompt。")
            return 1
        args.api_key = api_key

        output = generate_with_args(args)
    except LlmCallError as err:
        print(f"[错误] {err.kind}: {err}")
        print(f"       → {_KIND_TIP.get(err.kind, '')}")
        return 1
    except Exception as err:  # 兜底：任何未预期异常都给出可读信息而非裸traceback
        print(f"[未预期错误] {err}")
        print("       规则读取或文件写入等环节可能出问题；若可复现请把上述信息反馈给开发。")
        return 1

    print_hint(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())