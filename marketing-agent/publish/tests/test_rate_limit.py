from publish.rate_limit import RateLimiter, config, constraint
from publish.storage import PublishRecordStore


def _store(tmp_path):
    return PublishRecordStore(tmp_path / "records.sqlite3")


def test_default_constraints_are_one_per_day_and_24_hours():
    assert config.rate_limit_hours == 24
    assert constraint.daily_max == 1
    assert constraint.min_interval_hours == 24


def test_check_allows_account_with_no_published_record(tmp_path):
    limiter = RateLimiter(_store(tmp_path))

    result = limiter.check("xiaohongshu", "acct-1", now=1000.0)

    assert result.allowed is True
    assert result.reason == "ok"
    assert result.next_allowed_at == 1000.0


def test_check_rejects_before_24_hours_and_reports_next_time(tmp_path):
    store = _store(tmp_path)
    record_id = store.add_pending("xiaohongshu", "acct-1", "hash")
    store.mark_published(record_id, published_at=1000.0)
    limiter = RateLimiter(store)

    result = limiter.check("xiaohongshu", "acct-1", now=1000.0 + 23 * 3600)

    assert result.allowed is False
    assert "间隔" in result.reason
    assert result.next_allowed_at == 1000.0 + 24 * 3600


def test_check_allows_at_exactly_24_hours(tmp_path):
    store = _store(tmp_path)
    record_id = store.add_pending("douyin", "acct-2", "hash")
    store.mark_published(record_id, published_at=1000.0)
    limiter = RateLimiter(store)

    result = limiter.check("douyin", "acct-2", now=1000.0 + 24 * 3600)

    assert result.allowed is True
    assert result.reason == "ok"


def test_check_rejects_second_publication_with_daily_limit_reason(tmp_path):
    store = _store(tmp_path)
    record_id = store.add_pending("xiaohongshu", "acct-1", "hash")
    store.mark_published(record_id, published_at=1000.0)
    limiter = RateLimiter(store)

    result = limiter.check("xiaohongshu", "acct-1", now=1001.0)

    assert result.allowed is False
    assert "每日" in result.reason


def test_next_allowed_at_without_history_is_now(tmp_path):
    limiter = RateLimiter(_store(tmp_path))

    assert limiter.next_allowed_at("xiaohongshu", "acct-1", now=42.5) == 42.5
