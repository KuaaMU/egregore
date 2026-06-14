"""Topic — the core entity of Egregore.

A Topic is a conversation across multiple AI platforms.
It's not a single message — it's the entire lifecycle.

Example:
    Topic: "Redis Cache Architecture"
    ├── ChatGPT: https://chatgpt.com/c/xxx
    ├── Grok: https://grok.com/chat/xxx
    └── Kimi: https://kimi.moonshot.cn/chat/xxx

Egregore doesn't store the messages — the platforms do.
Egregore only stores the index (metadata + URLs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class Topic:
    """A conversation topic across multiple AI platforms.

    This is the core entity. Not Provider. Not Message. Topic.
    """

    id: str = field(default_factory=lambda: uuid4().hex[:6])
    title: str = ""
    providers: list[str] = field(default_factory=list)
    urls: dict[str, str] = field(default_factory=dict)  # provider -> conversation_url
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pinned: bool = False

    def touch(self) -> None:
        """Update last_accessed timestamp."""
        self.last_accessed = datetime.now(timezone.utc)

    def set_url(self, provider: str, url: str) -> None:
        """Record the conversation URL for a provider."""
        self.urls[provider] = url
        if provider not in self.providers:
            self.providers.append(provider)

    def get_url(self, provider: str) -> str | None:
        """Get the conversation URL for a provider."""
        return self.urls.get(provider)
