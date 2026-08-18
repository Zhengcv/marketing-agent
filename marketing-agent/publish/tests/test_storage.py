import sqlite3
import time
from pathlib import Path

from publish.storage import PublishRecordStore


def test_sqlite_file_is_created_and_pending_can_be_read(tmp_path):
    db_path = tmp_path / "records.sqlite3"
    store = PublishRecordStore(db_path)

    record_id = store.add_pending("xiaohongshu", "acct-1", "hash-1")

    assert db_path.exists()
    assert record_id == 1
    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute(
            "SELECT platform, account_id, content_hash, status, published_at "
            "FROM publish_records WHERE id = ?",
            (record_id,),
        ).fetchone()
    assert row == ("xiaohongshu", "acct-1", "hash-1", "pending", None)


def test_mark_published_updates_status_and_time(tmp_path):
    store = PublishRecordStore(tmp_path / "records.sqlite3")
    record_id = store.add_pending("douyin", "acct-2", "hash-2")

    store.mark_published(record_id, published_at=1234.5)

    assert store.latest_published_time("douyin", "acct-2") == 1234.5


def test_mark_aborted_does_not_count_as_published(tmp_path):
    store = PublishRecordStore(tmp_path / "records.sqlite3")
    record_id = store.add_pending("xiaohongshu", "acct-1", "hash-3")

    store.mark_aborted(record_id)

    assert store.latest_published_time("xiaohongshu", "acct-1") is None
    assert store.count_published_today("xiaohongshu", "acct-1", 0.0) == 0


def test_latest_published_time_returns_most_recent_record(tmp_path):
    store = PublishRecordStore(tmp_path / "records.sqlite3")
    first = store.add_pending("xiaohongshu", "acct-1", "first")
    second = store.add_pending("xiaohongshu", "acct-1", "second")
    store.mark_published(first, published_at=100.0)
    store.mark_published(second, published_at=200.0)

    assert store.latest_published_time("xiaohongshu", "acct-1") == 200.0


def test_count_published_today_filters_platform_account_and_start(tmp_path):
    store = PublishRecordStore(tmp_path / "records.sqlite3")
    matching = store.add_pending("xiaohongshu", "acct-1", "matching")
    old = store.add_pending("xiaohongshu", "acct-1", "old")
    other_account = store.add_pending("xiaohongshu", "acct-2", "other")
    other_platform = store.add_pending("douyin", "acct-1", "other-platform")
    store.mark_published(matching, published_at=100.0)
    store.mark_published(old, published_at=99.9)
    store.mark_published(other_account, published_at=100.0)
    store.mark_published(other_platform, published_at=100.0)

    assert store.count_published_today("xiaohongshu", "acct-1", 100.0) == 1
