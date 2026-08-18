"""Hard publishing frequency limits.

The limiter deliberately keeps policy small and explicit: one published post per
account per calendar day, and at least 24 hours between published posts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .storage import PublishRecordStore


@dataclass(frozen=True)
class _Config:
    rate_limit_hours: int = 24


@dataclass(frozen=True)
class _Constraint:
    daily_max: int = 1
    min_interval_hours: int = 24


config = _Config()
constraint = _Constraint()


@dataclass
class RateLimitResult:
    allowed: bool
    reason: str
    next_allowed_at: Optional[float]


class RateLimiter:
    def __init__(self, storage: PublishRecordStore):
        self._storage = storage

    @staticmethod
    def _today_start(timestamp: float) -> float:
        """Return local-midnight timestamp for ``timestamp``."""
        local_time = datetime.fromtimestamp(timestamp)
        elapsed_today = (
            local_time.hour * 3600
            + local_time.minute * 60
            + local_time.second
            + local_time.microsecond / 1000000.0
        )
        # Subtracting from the supplied timestamp avoids platform-specific
        # failures when tests intentionally use pre-1970 timestamps.
        return timestamp - elapsed_today

    def check(
        self,
        platform: str,
        account_id: str,
        now: Optional[float] = None,
    ) -> RateLimitResult:
        """Check whether an account may publish at ``now``."""
        current = time.time() if now is None else float(now)
        latest = self._storage.latest_published_time(platform, account_id)
        interval_end = None
        interval_blocked = False
        if latest is not None:
            interval_end = latest + constraint.min_interval_hours * 3600
            interval_blocked = current < interval_end

        today_start = self._today_start(current)
        published_today = self._storage.count_published_today(
            platform, account_id, today_start
        )
        daily_blocked = published_today >= constraint.daily_max
        if daily_blocked or interval_blocked:
            reasons = []
            if daily_blocked:
                reasons.append("已达到每日发布上限1篇")
            if interval_blocked:
                reasons.append("发布间隔不足24小时")
            next_at = interval_end if interval_blocked else self.next_allowed_at(
                platform, account_id, current
            )
            return RateLimitResult(
                allowed=False,
                reason="；".join(reasons),
                next_allowed_at=next_at,
            )

        return RateLimitResult(allowed=True, reason="ok", next_allowed_at=current)

    def config_daily_unit(self) -> int:
        """Return the hard daily publishing limit."""
        return constraint.daily_max

    def next_allowed_at(
        self,
        platform: str,
        account_id: str,
        now: Optional[float] = None,
    ) -> float:
        """Return the earliest timestamp at which publishing is allowed."""
        current = time.time() if now is None else float(now)
        latest = self._storage.latest_published_time(platform, account_id)
        if latest is None:
            return current
        return max(current, latest + constraint.min_interval_hours * 3600)
