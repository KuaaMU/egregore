"""TopicManager — the 4 actions with observability.

1. create() — create topic, open tabs, save metadata, emit event
2. send()  — send prompt to all providers, emit events
3. close() — close tabs, keep metadata, emit event
4. reopen() — restore tabs from URLs, emit event

Every action emits events. This is how we learn real usage patterns.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog

from egregore.providers.cdp_transport import CdpTransport
from egregore.topic.events import TopicEventStore, TopicEventType
from egregore.topic.models import Topic
from egregore.topic.store import TopicStore

logger = structlog.get_logger()


@dataclass
class SendResult:
    """Result of sending a prompt to a topic."""

    provider: str
    content: str
    success: bool
    latency_ms: float
    url: str = ""


class TopicManager:
    """Manages topic lifecycle with observability."""

    def __init__(self, transport: CdpTransport, store: TopicStore, event_store: TopicEventStore) -> None:
        self._transport = transport
        self._store = store
        self._events = event_store
        self._active_topics: dict[str, Topic] = {}

    async def create(self, title: str, providers: list[str]) -> Topic:
        """Create a new topic and open tabs for each provider."""
        topic = Topic(title=title, providers=providers)

        for provider in providers:
            url = self._provider_url(provider)
            try:
                page = await self._transport._browser_manager.get_page(url)
                topic.set_url(provider, page.url)
                self._events.record(topic.id, TopicEventType.PAGE_CREATED, provider, page.url)
                logger.info("topic_tab_opened", topic=topic.id, provider=provider)
            except Exception as e:
                self._events.record(topic.id, TopicEventType.PROVIDER_FAILED, provider, str(e))
                logger.error("topic_tab_failed", topic=topic.id, provider=provider, error=str(e))

        self._store.save(topic)
        self._active_topics[topic.id] = topic
        self._events.record(topic.id, TopicEventType.CREATED, detail=title)

        logger.info("topic_created", topic=topic.id, title=title, providers=providers)
        return topic

    async def send(self, topic_id: str, prompt: str, timeout_ms: int = 60000) -> list[SendResult]:
        """Send a prompt to all providers in a topic. Reuses existing tabs."""
        topic = self._active_topics.get(topic_id) or self._store.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        topic.touch()
        self._events.record(topic_id, TopicEventType.SENT, detail=prompt[:100])

        results = []
        for provider in topic.providers:
            url = topic.get_url(provider) or self._provider_url(provider)
            try:
                response = await self._transport.send(url, prompt, timeout_ms)
                results.append(SendResult(
                    provider=provider,
                    content=response.content,
                    success=response.success,
                    latency_ms=response.latency_ms,
                    url=url,
                ))
                if response.success:
                    topic.set_url(provider, url)
                else:
                    self._events.record(topic_id, TopicEventType.PROVIDER_FAILED, provider, response.error or "")
            except Exception as e:
                results.append(SendResult(provider=provider, content="", success=False, latency_ms=0, url=url))
                self._events.record(topic_id, TopicEventType.PROVIDER_FAILED, provider, str(e))

        self._store.save(topic)
        return results

    async def close(self, topic_id: str) -> None:
        """Close a topic's tabs. Keep metadata."""
        topic = self._active_topics.pop(topic_id, None)
        if not topic:
            return

        for provider in topic.providers:
            url = topic.get_url(provider)
            if url and url in self._transport._browser_manager._pages:
                page = self._transport._browser_manager._pages.pop(url)
                try:
                    await page.close()
                except Exception:
                    pass

        self._store.save(topic)
        self._events.record(topic_id, TopicEventType.CLOSED)
        logger.info("topic_closed", topic=topic_id)

    async def reopen(self, topic_id: str) -> Topic:
        """Reopen a topic by navigating to saved URLs."""
        topic = self._store.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        for provider in topic.providers:
            url = topic.get_url(provider)
            if url:
                try:
                    page = await self._transport._browser_manager.get_page(url)
                    self._events.record(topic_id, TopicEventType.PAGE_REUSED, provider)
                    logger.info("topic_tab_reopened", topic=topic_id, provider=provider)
                except Exception as e:
                    self._events.record(topic_id, TopicEventType.PROVIDER_FAILED, provider, str(e))

        topic.touch()
        self._store.save(topic)
        self._active_topics[topic_id] = topic
        self._events.record(topic_id, TopicEventType.REOPENED)
        return topic

    def list_topics(self) -> list[Topic]:
        return self._store.list_all()

    def delete_topic(self, topic_id: str) -> None:
        self._active_topics.pop(topic_id, None)
        self._store.delete(topic_id)

    def get_topic_stats(self, topic_id: str) -> dict:
        """Get observability stats for a topic."""
        return self._events.get_stats(topic_id)

    def _provider_url(self, provider: str) -> str:
        urls = {
            "chatgpt": "https://chatgpt.com/",
            "grok": "https://grok.com/",
            "kimi": "https://kimi.moonshot.cn/",
            "qwen": "https://tongyi.aliyun.com/qianwen/",
            "doubao": "https://www.doubao.com/",
        }
        return urls.get(provider, "")
