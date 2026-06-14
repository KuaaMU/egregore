"""TopicStore — SQLite storage for topic metadata.

Only stores metadata. Never stores message content.
The platforms (ChatGPT, Grok, etc.) store the actual conversations.

Schema:
    topics: id, title, created_at, last_accessed, pinned
    topic_providers: topic_id, provider, conversation_url
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from egregore.topic.models import Topic

DEFAULT_DB_PATH = Path.home() / ".egregore" / "topics.db"


class TopicStore:
    """SQLite-backed topic metadata store."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                pinned INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS topic_providers (
                topic_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                conversation_url TEXT DEFAULT '',
                PRIMARY KEY (topic_id, provider),
                FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
            );
        """)

    def save(self, topic: Topic) -> None:
        """Save or update a topic."""
        self._conn.execute(
            "INSERT OR REPLACE INTO topics (id, title, created_at, last_accessed, pinned) VALUES (?, ?, ?, ?, ?)",
            (topic.id, topic.title, topic.created_at.isoformat(), topic.last_accessed.isoformat(), int(topic.pinned)),
        )
        for provider in topic.providers:
            url = topic.urls.get(provider, "")
            self._conn.execute(
                "INSERT OR REPLACE INTO topic_providers (topic_id, provider, conversation_url) VALUES (?, ?, ?)",
                (topic.id, provider, url),
            )
        self._conn.commit()

    def get(self, topic_id: str) -> Topic | None:
        """Get a topic by ID."""
        row = self._conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if not row:
            return None
        return self._row_to_topic(row)

    def list_all(self, limit: int = 50) -> list[Topic]:
        """List all topics, most recent first."""
        rows = self._conn.execute(
            "SELECT * FROM topics ORDER BY pinned DESC, last_accessed DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_topic(row) for row in rows]

    def delete(self, topic_id: str) -> None:
        """Delete a topic and its provider mappings."""
        self._conn.execute("DELETE FROM topic_providers WHERE topic_id = ?", (topic_id,))
        self._conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        self._conn.commit()

    def _row_to_topic(self, row) -> Topic:
        """Convert a database row to a Topic."""
        providers_rows = self._conn.execute(
            "SELECT provider, conversation_url FROM topic_providers WHERE topic_id = ?", (row["id"],)
        ).fetchall()
        providers = [r["provider"] for r in providers_rows]
        urls = {r["provider"]: r["conversation_url"] for r in providers_rows}

        return Topic(
            id=row["id"],
            title=row["title"],
            providers=providers,
            urls=urls,
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed=datetime.fromisoformat(row["last_accessed"]),
            pinned=bool(row["pinned"]),
        )

    def close(self) -> None:
        self._conn.close()
