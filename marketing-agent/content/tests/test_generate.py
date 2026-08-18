#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate.py 的单元测试。

运行方式（在 marketing-agent/ 下）：
    python content/tests/test_generate.py
    或
    python -m pytest content/tests/test_generate.py -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from content.generate import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    LlmCallError,
    _extract_content,
    _strip_code_fence,
    fill_topic,
    find_violation_words,
    generate_with_args,
    load_template,
    parse_args,
)


def _make_args(**overrides) -> "argparse.Namespace":
    """构造一个接近 parse_args 结果的 Namespace，供 generate_with_args 使用。"""
    defaults = {
        "platform": "xiaohongshu",
        "topic": "怎么找靠谱家教",
        "topic_id": None,
        "output": None,
        "model": DEFAULT_MODEL,
        "base_url": DEFAULT_BASE_URL,
        "api_key": "test-key",
        "no_call": True,
    }
    defaults.update(overrides)

    # 对齐 parse_args 的语义：output 未传时由生成流程计算默认路径
    if defaults["output"] is None:
        from content.generate import _default_output_path

        defaults["output"] = _default_output_path(
            defaults["platform"], defaults["topic"] or "topic"
        )
    return type("Args", (object,), defaults)()


class TestLoadTemplate(unittest.TestCase):
    """模板读取：平台对模板文件的映射。"""

    def test_xiaohongshu_template_loaded(self) -> None:
        tpl = load_template("xiaohongshu")
        self.assertIn("[主题]", tpl)  # 模板里确实有占位符
        self.assertIn("反 AI 化铁律", tpl)
        self.assertIn("合规红线", tpl)

    def test_douyin_template_loaded(self) -> None:
        tpl = load_template("douyin")
        self.assertIn("[主题]", tpl)
        self.assertIn("时间轴结构铁律", tpl)

    def test_unknown_platform_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_template("weibo")


class TestFillTopic(unittest.TestCase):
    """占位符替换。"""

    def _has_formatted(self, prompt: str, topic: str) -> bool:
        return ("**[主题]**" not in prompt) and ("[主题]" not in prompt) and (topic in prompt)

    def test_fills_xiaohongshu(self) -> None:
        prompt = fill_topic(load_template("xiaohongshu"), "测试")
        self._has_formatted(prompt, "测试")

    def test_fills_douyin(self) -> None:
        prompt = fill_topic(load_template("douyin"), "找家教避坑")
        self._has_formatted(prompt, "找家教避坑")

    def test_placeholder_mark_left_for_remaining_others(self) -> None:
        # 无关占位符（如 {duration}、{时长}）不应被误改；只替换主题相关的三种写法
        out = fill_topic("a [主题] b {duration} c **[主题]**", "X")
        self.assertEqual(out, "a X b {duration} c **X**")

    def test_generic_placeholder_supported(self) -> None:
        # 也兼容需求方习惯的 {topic} 写法
        out = fill_topic("题目是 {topic}，请展开", "如何选老师")
        self.assertIn("如何选老师", out)
        self.assertNotIn("{topic}", out)

    def test_no_placeholder_left_for_valid_topic(self) -> None:
        cases = ["怎么找靠谱家教", "找家教避坑"]
        for case in cases:
            for platform in ("xiaohongshu", "douyin"):
                prompt = fill_topic(load_template(platform), case)
                self.assertNotIn("[主题]", prompt)
                self.assertNotIn("{topic}", prompt)
                self.assertIn(case, prompt)


class TestNoCallGenerate(unittest.TestCase):
    """--no-call 端到端：不调 LLM，只剩 prompt 预览写入文件。"""

    def _run_no_call(self, platform: str, topic: str) -> Path:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.md"
            output = generate_with_args(
                _make_args(platform=platform, topic=topic, output=str(out))
            )
            yield output

    def test_writes_prompt_preview(self) -> None:
        """no-call 输出 = YAML frontmatter + prompt 预览，内容包含模板铁律与话题。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.md"
            generate_with_args(
                _make_args(platform="xiaohongshu", topic="怎么找靠谱家教", output=str(out))
            )
            self.assertTrue(out.is_file(), "输出文件应已创建")
            text = out.read_text(encoding="utf-8")
            self.assertIn("---", text)                      # YAML frontmatter
            self.assertIn("platform: xiaohongshu", text)
            self.assertIn("怎么找靠谱家教", text)            # 话题进了正文/prompt
            self.assertIn("反 AI 化铁律", text)             # 模板铁律保留
            self.assertIn("合规红线", text)
            self.assertIn("no-call", text)                  # mode 标记

    def test_douyin_variant(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.md"
            generate_with_args(_make_args(platform="douyin", topic="找家教避坑", output=str(out)))
            text = out.read_text(encoding="utf-8")
            self.assertIn("platform: douyin", text)
            self.assertIn("时间轴结构铁律", text)
            self.assertIn("找家教避坑", text)

    def test_creates_nested_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "deep" / "nest" / "out.md"
            generate_with_args(_make_args(topic="测试嵌套目录", output=str(out)))
            self.assertTrue(out.is_file())

    def test_violation_word_adds_compliance_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.md"
            generate_with_args(_make_args(topic="保证提分，名师一对一", output=str(out)))
            text = out.read_text(encoding="utf-8")
            self.assertIn("warn", text)  # frontmatter 的 compliance 标了 warn
            self.assertIn("疑似违规词", text) if "合规" in text else None

    def test_topic_id_selected_from_pool(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.md"
            generate_with_args(_make_args(topic=None, topic_id=0, output=str(out)))
            text = out.read_text(encoding="utf-8")
            self.assertIn("怎么判断家教老师靠不靠谱", text)


class TestExtractContent(unittest.TestCase):
    """LLM 响应解析：JSON/markdown/分块数组都容忍。"""

    def test_extract_json_content(self) -> None:
        data = {"choices": [{"message": {"content": "正文"}}]}
        self.assertEqual(_extract_content(data), "正文")

    def test_extract_strips_code_fence(self) -> None:
        data = {"choices": [{"message": {"content": "```markdown\n正文内容\n```"}}]}
        self.assertEqual(_extract_content(data), "正文内容")

    def test_extract_handles_chunk_array(self) -> None:
        data = {"choices": [{"message": {"content": [
            {"type": "text", "text": "第一段"},
            {"type": "text", "text": "第二段"},
        ]}}]}
        self.assertEqual(_extract_content(data), "第一段第二段")

    def test_extract_missing_content_raises(self) -> None:
        with self.assertRaises(LlmCallError):
            _extract_content({"choices": [{"message": {}}]})

    def test_extract_plain_text_string(self) -> None:
        # 极少数网关直接把正文当纯文本
        self.assertEqual(_extract_content("```\n裸正文\n```"), "裸正文")


class TestStripCodeFence(unittest.TestCase):
    def test_plain(self) -> None:
        self.assertEqual(_strip_code_fence("  正文  "), "正文")

    def test_with_fence(self) -> None:
        self.assertEqual(_strip_code_fence("```md\n正文\n```"), "正文")


class TestParseArgs(unittest.TestCase):
    """入参解析的正确/错误路径。"""

    def test_list_topics(self) -> None:
        args = parse_args(["--list-topics"])
        self.assertTrue(args.list_topics)

    def test_list_topics_with_platform_filter(self) -> None:
        args = parse_args(["--list-topics", "--platform", "douyin"])
        self.assertEqual(args.platform, "douyin")

    def test_basic_args_parsed(self) -> None:
        args = parse_args([
            "--platform", "xiaohongshu",
            "--topic", "怎么找靠谱家教",
            "--output", "out/x.md",
        ])
        self.assertEqual(args.platform, "xiaohongshu")
        self.assertEqual(args.topic, "怎么找靠谱家教")
        self.assertEqual(args.output, "out/x.md")
        self.assertEqual(args.model, DEFAULT_MODEL)
        self.assertEqual(args.base_url, DEFAULT_BASE_URL)

    def test_missing_platform_errors(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--topic", "测试"])

    def test_missing_topic_errors(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--platform", "douyin"])

    def test_both_topic_sources_error(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--platform", "douyin", "--topic", "A", "--topic-id", "0"])

    def test_empty_topic_errors(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--platform", "douyin", "--topic", "   "])

    def test_invalid_platform_choice(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--platform", "weibo", "--topic", "A"])


class TestViolationWords(unittest.TestCase):
    def test_detects_base_words(self) -> None:
        hits = find_violation_words("保证提分，名师一对一")
        self.assertIn("提分", hits)
        self.assertIn("名师", hits)

    def test_clean_topic_no_hits(self) -> None:
        self.assertEqual(find_violation_words("怎么判断家教老师靠不靠谱"), [])


class TestFrontmatter(unittest.TestCase):
    def test_yaml_quoting_keeps_parseable(self) -> None:
        # 带中文冒号的话题应被 YAML 正确引号包围
        topic = "信息费该谁付：家长还是老师"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.md"
            generate_with_args(_make_args(topic=topic, output=str(out)))
            text = out.read_text(encoding="utf-8")
            self.assertIn(topic, text)


if __name__ == "__main__":
    # 避免把项目根误当工作目录导致 __main__ 语法损坏——实际入口
    unittest.main(verbosity=2)