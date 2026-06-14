"""TopicRuntime — in-memory runtime for a topic.

Topic (SQLite) = metadata, persisted
TopicRuntime (Memory) = live state, not persisted

The runtime manages:
- Pages (one per provider)
- State (ACTIVE/IDLE/CLOSED)
- Metrics (open_count, page_reuse_count, etc.)
- Auto-recovery (page closed? reopen it)

This is the bridge between Topic metadata and live browser pages.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import structlog
from playwright.async_api import Page

from egregore.providers.browser_manager import BrowserManager
from egregore.topic.events import TopicEventStore, TopicEventType
from egregore.topic.models import Topic

logger = structlog.get_logger()


class TopicState(str, Enum):
    ACTIVE = "active"   # Currently in use
    IDLE = "idle"       # Not used recently, but pages still open
    CLOSED = "closed"   # Pages closed, only metadata remains


@dataclass
class TopicMetrics:
    """Runtime metrics for a topic. Not persisted."""

    open_count: int = 0
    reopen_count: int = 0
    page_create_count: int = 0
    page_reuse_count: int = 0
    provider_failure_count: int = 0
    provider_recovery_count: int = 0
    send_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TopicRuntime:
    """In-memory runtime for a topic.

    Manages live browser pages and tracks state.
    Not persisted — recreated from Topic metadata on reopen.
    """

    def __init__(
        self,
        topic: Topic,
        browser_manager: BrowserManager,
        event_store: TopicEventStore,
    ) -> None:
        self.topic = topic
        self._browser_manager = browser_manager
        self._events = event_store
        self.pages: dict[str, Page] = {}  # provider -> page
        self.state = TopicState.ACTIVE
        self.metrics = TopicMetrics()

    async def open_pages(self) -> None:
        """Open or reuse pages for all providers in the topic."""
        for provider in self.topic.providers:
            url = self.topic.get_url(provider)
            if not url:
                continue

            try:
                page = await self._browser_manager.get_page(url)

                # Check if page is still alive
                if page.is_closed():
                    # Auto-recover: navigate to URL again
                    page = await self._recover_page(provider, url)
                    self.metrics.provider_recovery_count += 1
                    self._events.record(self.topic.id, TopicEventType.PROVIDER_RECOVERED, provider)

                self.pages[provider] = page
                self.metrics.open_count += 1

                # Track page reuse vs creation
                if page.url == url:
                    self.metrics.page_reuse_count += 1
                    self._events.record(self.topic.id, TopicEventType.PAGE_REUSED, provider)
                else:
                    self.metrics.page_create_count += 1
                    self._events.record(self.topic.id, TopicEventType.PAGE_CREATED, provider, page.url)

            except Exception as e:
                self.metrics.provider_failure_count += 1
                self._events.record(self.topic.id, TopicEventType.PROVIDER_FAILED, provider, str(e))
                logger.error("runtime_page_failed", topic=self.topic.id, provider=provider, error=str(e))

        self.state = TopicState.ACTIVE
        self.metrics.last_active = datetime.now(timezone.utc)

    async def get_page(self, provider: str) -> Page | None:
        """Get a page for a provider. Auto-recover if closed."""
        page = self.pages.get(provider)
        if page and not page.is_closed():
            return page

        # Page was closed — auto-recover
        url = self.topic.get_url(provider)
        if url:
            page = await self._recover_page(provider, url)
            self.pages[provider] = page
            return page

        return None

    async def close_pages(self) -> None:
        """Close all pages. Transition to CLOSED."""
        for provider, page in self.pages.items():
            try:
                if not page.is_closed():
                    await page.close()
            except Exception:
                pass
        self.pages.clear()
        self.state = TopicState.CLOSED
        self._events.record(self.topic.id, TopicEventType.CLOSED)

    async def _recover_page(self, provider: str, url: str) -> Page:
        """Recover a closed page by navigating to the conversation URL."""
        logger.info("runtime_page_recovery", topic=self.topic.id, provider=provider, url=url)
        page = await self._browser_manager.get_page(url)
        self.metrics.provider_recovery_count += 1
        return page

    def touch(self) -> None:
        """Update last_active timestamp."""
        self.metrics.last_active = datetime.now(timezone.utc)
        self.metrics.send_count += 1
