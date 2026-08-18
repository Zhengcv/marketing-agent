from publish.run import main, run_workflow
from publish.storage import PublishRecordStore


class _PublisherSpy:
    def __init__(self):
        self.fill_calls = []
        self.publish_calls = 0

    def fill_form(self, payload):
        self.fill_calls.append(payload)
        return {"title": payload["title"], "tags": payload["tags"]}

    def publish(self):
        self.publish_calls += 1


def test_live_flag_is_rejected_without_publishing(capsys):
    exit_code = main(
        [
            "--platform", "xiaohongshu",
            "--account", "acct-1",
            "--title", "标题",
            "--content", "正文",
            "--live",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "人工发布" in captured.err


def test_default_dry_run_only_previews_and_does_not_publish(tmp_path, capsys):
    publisher = _PublisherSpy()
    store = PublishRecordStore(tmp_path / "records.sqlite3")

    exit_code = run_workflow(
        platform="xiaohongshu",
        account_id="acct-1",
        title="标题",
        content="正文",
        tags=["家教"],
        store=store,
        publisher=publisher,
        input_fn=lambda _prompt: "y",
        now=100000.0,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "发布预览" in captured.out
    assert "dry-run" in captured.out
    assert publisher.publish_calls == 0
    assert store.latest_published_time("xiaohongshu", "acct-1") is None


def test_frequency_rejection_is_printed_and_stub_is_not_called(tmp_path, capsys):
    store = PublishRecordStore(tmp_path / "records.sqlite3")
    record_id = store.add_pending("xiaohongshu", "acct-1", "old")
    store.mark_published(record_id, published_at=100000.0)
    publisher = _PublisherSpy()

    exit_code = run_workflow(
        platform="xiaohongshu",
        account_id="acct-1",
        title="标题",
        content="正文",
        store=store,
        publisher=publisher,
        input_fn=lambda _prompt: "y",
        now=100001.0,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "频控拒绝" in captured.out
    assert publisher.fill_calls == []
    assert publisher.publish_calls == 0
