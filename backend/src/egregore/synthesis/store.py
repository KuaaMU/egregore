"""Response Store — saves raw responses to disk.

During Dogfooding, we collect real prompt→response data.
This data will drive Synthesis design later.

Storage: ~/.egregore/responses/<topic_id>/<timestamp>.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DIR = Path.home() / ".egregore" / "responses"


class ResponseStore:
    """Saves raw round table responses to disk."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or DEFAULT_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, topic_id: str, prompt: str, responses: dict[str, str]) -> Path:
        """Save a round table result.

        Args:
            topic_id: Topic ID
            prompt: The prompt sent
            responses: provider_id → response text

        Returns:
            Path to saved file
        """
        topic_dir = self._base_dir / topic_id
        topic_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filepath = topic_dir / f"{timestamp}.json"

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic_id": topic_id,
            "prompt": prompt,
            "responses": responses,
            "provider_count": len(responses),
            "response_lengths": {pid: len(text) for pid, text in responses.items()},
        }

        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return filepath

    def load(self, topic_id: str) -> list[dict]:
        """Load all responses for a topic."""
        topic_dir = self._base_dir / topic_id
        if not topic_dir.exists():
            return []

        results = []
        for f in sorted(topic_dir.glob("*.json")):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                continue
        return results

    def load_all(self) -> list[dict]:
        """Load all responses across all topics."""
        results = []
        for topic_dir in self._base_dir.iterdir():
            if topic_dir.is_dir():
                results.extend(self.load(topic_dir.name))
        return results

    def count(self) -> int:
        """Count total saved responses."""
        return len(list(self._base_dir.rglob("*.json")))
