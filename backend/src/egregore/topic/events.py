"""Topic Events — observability for topic lifecycle.

Every state change is an event. Events are stored in SQLite.
This lets us understand real usage patterns before adding features.

Pattern: Event Sourcing (lightweight)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4


class TopicEventType(str, Enum):
    CREATED = "created"
    OPENED = "opened"
    CLOSED = "closed"
    REOPENED = "reopened"
    SENT = "sent"
    PAGE_REUSED = "page_reused"
    PAGE_CREATED = "page_created"
    PROVIDER_FAILED = "provider_failed"
    PROVIDER_RECOVERED = "provider_recovered"


class TopicEventStore:
    """SQLite-backed event log for topic lifecycle."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS topic_events (
                id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                provider TEXT DEFAULT '',
                detail TEXT DEFAULT '',
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_topic_events_topic ON topic_events(topic_id);
            CREATE INDEX IF NOT EXISTS idx_topic_events_type ON topic_events(event_type);
        """)

    def record(self, topic_id: str, event_type: TopicEventType, provider: str = "", detail: str = "") -> None:
        """Record a topic event."""
        self._conn.execute(
            "INSERT INTO topic_events (id, topic_id, event_type, provider, detail, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (uuid4().hex[:12], topic_id, event_type.value, provider, detail, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def get_events(self, topic_id: str, limit: int = 100) -> list[dict]:
        """Get events for a topic."""
        rows = self._conn.execute(
            "SELECT * FROM topic_events WHERE topic_id = ? ORDER BY timestamp DESC LIMIT ?",
            (topic_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self, topic_id: str) -> dict:
        """Get aggregated stats for a topic."""
        rows = self._conn.execute(
            "SELECT event_type, COUNT(*) as count FROM topic_events WHERE topic_id = ? GROUP BY event_type",
            (topic_id,),
        ).fetchall()
        return {row["event_type"]: row["count"] for row in rows}
