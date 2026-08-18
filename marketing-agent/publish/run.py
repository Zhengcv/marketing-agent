"""半自动发布流程命令行入口。

默认流程只使用离线 mock publisher：合规检查 -> 填表 -> 预览 ->
人工确认 -> 写回 SQLite。真实平台发布被明确禁用。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import os
from pathlib import Path
import sys
from typing import Callable, List, Optional

from .human_gate import GateDecision, HumanGate
from .rate_limit import RateLimiter
from .storage import PublishRecordStore


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "publish_records.sqlite3"


def _ensure_utf8_stdout() -> None:
    """Use UTF-8 output even when Windows starts with a GBK console."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            return
        except (AttributeError, OSError):
            pass
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        sys.stdout = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")


class _UnittestPublisher:
    """Publisher stub that records browser-like operations but never goes online."""

    def __init__(self, platform: str):
        self.platform = platform
        self.published = False
        try:
            from browser.engine import UnittestEngine
            self.engine = UnittestEngine()
        except ImportError:
            self.engine = None

    def fill_form(self, payload: dict) -> dict:
        if self.engine is not None:
            self.engine.navigate("mock://{}/publish".format(self.platform))
            self.engine.fill_form(payload)
        body = payload.get("content", "")
        return {
            "platform": self.platform,
            "title": payload.get("title", ""),
            "body_summary": body[:80] + ("..." if len(body) > 80 else ""),
            "tags": list(payload.get("tags", [])),
        }

    def publish(self) -> None:
        """This method is intentionally never called by the dry-run workflow."""
        self.published = True
        if self.engine is not None:
            self.engine.click("#publish-btn")


def _content_hash(title: str, content: str, tags: List[str]) -> str:
    canonical = "\n".join([title, content, "\x1f".join(tags)])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compliance_check(content: str) -> bool:
    """Run the existing compliance gate when it is available."""
    try:
        from compliance.check import check_text
    except (ImportError, OSError):
        print("[info] 合规闸未集成，已跳过")
        return True
    try:
        verdict = check_text(content).verdict
    except Exception as exc:
        print("[info] 合规闸不可用，已跳过: {}".format(exc))
        return True
    print("合规检查: {}".format(verdict))
    if verdict == "block":
        print("合规拒绝：文案未通过合规闸")
        return False
    return True


def _quality_check(content: str) -> None:
    """Report the optional quality review without blocking dry-run preview."""
    try:
        from quality.expert_panel import review_content
    except (ImportError, OSError):
        print("[info] 质量门未集成，已跳过")
        return
    try:
        report = review_content(content)
        print("质量检查: {}".format(report.verdict))
    except Exception as exc:
        print("[info] 质量门不可用，已跳过: {}".format(exc))


def _load_stub(spec: str, platform: str):
    """Load ``module:attribute`` publisher stubs for tests/demos."""
    if ":" not in spec:
        raise ValueError("publisher stub 必须使用 module:attribute 格式")
    module_name, attribute = spec.split(":", 1)
    factory = getattr(importlib.import_module(module_name), attribute)
    try:
        return factory(platform)
    except TypeError:
        return factory()


def run_workflow(
    platform: str,
    account_id: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    store: Optional[PublishRecordStore] = None,
    publisher=None,
    input_fn: Optional[Callable[[str], str]] = None,
    now: Optional[float] = None,
    dry_run: bool = True,
) -> int:
    """Run one guarded publish attempt; return a CLI-style status code."""
    if not dry_run:
        print("真实发布已禁用，请在浏览器中人工发布。", file=sys.stderr)
        return 2
    tags = list(tags or [])
    store = store or PublishRecordStore(Path(os.environ.get("PUBLISH_DB_PATH", DEFAULT_DB_PATH)))
    limiter = RateLimiter(store)
    rate_result = limiter.check(platform, account_id, now=now)
    if not rate_result.allowed:
        print("频控拒绝: {}".format(rate_result.reason))
        if rate_result.next_allowed_at is not None:
            print("下次允许时间戳: {:.3f}".format(rate_result.next_allowed_at))
        return 1

    if not _compliance_check(content):
        return 2
    _quality_check(content)

    payload = {"title": title, "content": content, "tags": tags}
    publisher = publisher or _UnittestPublisher(platform)
    record_id = store.add_pending(platform, account_id, _content_hash(title, content, tags))
    try:
        summary = publisher.fill_form(payload)
        preview = HumanGate(input_fn=input_fn).generate_preview(platform, summary)
        print(preview)
        result = HumanGate(input_fn=input_fn).request_confirm(preview)
        if result.decision is GateDecision.CONFIRM:
            store.mark_aborted(record_id)
            print("人工确认完成；dry-run 不调用真实发布，已写回 aborted。")
            return 0
        store.mark_aborted(record_id)
        print("发布已取消，已写回 aborted。")
        return 0
    except Exception as exc:
        store.mark_aborted(record_id)
        print("发布流程失败，已写回 aborted: {}".format(exc), file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="营销 Agent 半自动发布（默认 dry-run）")
    parser.add_argument("--platform", required=True, choices=("xiaohongshu", "douyin"))
    parser.add_argument("--account", required=True, dest="account_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--content", "--body", required=True, dest="content")
    parser.add_argument("--tags", nargs="*", default=[])
    parser.add_argument("--mock", action="store_true", help="使用离线 mock（默认行为）")
    parser.add_argument("--publisher-stub", help=argparse.SUPPRESS)
    parser.add_argument("--live", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--db", type=Path, help="SQLite 文件路径")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    _ensure_utf8_stdout()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.live:
        print("--live 不可用；请在浏览器中人工发布。", file=sys.stderr)
        return 2
    publisher = None
    stub_spec = args.publisher_stub or os.environ.get("PUBLISHER_STUB")
    if stub_spec:
        try:
            publisher = _load_stub(stub_spec, args.platform)
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            print("publisher stub 加载失败: {}".format(exc), file=sys.stderr)
            return 2
    store = PublishRecordStore(args.db or Path(os.environ.get("PUBLISH_DB_PATH", DEFAULT_DB_PATH)))
    return run_workflow(
        platform=args.platform,
        account_id=args.account_id,
        title=args.title,
        content=args.content,
        tags=args.tags,
        store=store,
        publisher=publisher,
        dry_run=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
