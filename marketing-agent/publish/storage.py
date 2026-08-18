"""SQLite storage for publish attempts and their outcomes."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PublishRecord:
    """A persisted publishing attempt."""

    id: int
    platform: str
    account_id: str
    content_hash: str
    status: str
    created_at: float
    published_at: Optional[float]


class PublishRecordStore:
    """SQLite-backed store for publish records."""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        if str(self._db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        """Create the publish-record table when it does not exist."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publish_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'published', 'aborted')),
                    created_at REAL NOT NULL,
                    published_at REAL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_publish_records_account_time
                ON publish_records (platform, account_id, status, published_at)
                """
            )

    def add_pending(self, platform: str, account_id: str, content_hash: str) -> int:
        """Insert a pending record and return its generated id."""
        created_at = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO publish_records
                    (platform, account_id, content_hash, status, created_at, published_at)
                VALUES (?, ?, ?, 'pending', ?, NULL)
                """ ,
                (platform, account_id, content_hash, created_at),
            )
            return int(cursor.lastrowid)

    def mark_published(self, record_id: int, published_at: Optional[float] = None) -> None:
        """Mark a record as published, using the current time by default."""
        published_at = time.time() if published_at is None else published_at
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE publish_records
                SET status = 'published', published_at = ?
                WHERE id = ?
                """,
                (published_at, record_id),
            )

    def mark_aborted(self, record_id: int) -> None:
        """Mark a pending attempt as aborted."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE publish_records
                SET status = 'aborted', published_at = NULL
                WHERE id = ?
                """,
                (record_id,),
            )

    def latest_published_time(self, platform: str, account_id: str) -> Optional[float]:
        """Return the latest published timestamp for a platform/account pair."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT published_at
                FROM publish_records
                WHERE platform = ? AND account_id = ?
                  AND status = 'published' AND published_at IS NOT NULL
                ORDER BY published_at DESC, id DESC
                LIMIT 1
                """,
                (platform, account_id),
            ).fetchone()
        return None if row is None else float(row["published_at"])

    def count_published_today(self, platform: str, account_id: str, today_start: float) -> int:
        """Count published records at or after ``today_start``."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM publish_records
                WHERE platform = ? AND account_id = ?
                  AND status = 'published' AND published_at >= ?
                """,
                (platform, account_id, today_start),
            ).fetchone()
        return int(row["count"])
