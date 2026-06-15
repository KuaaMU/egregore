"""TopicManager — lifecycle management with TopicRuntime.

Architecture:
    Topic (SQLite metadata)
        ↓
    TopicRuntime (in-memory, not persisted)
        ↓
    BrowserManager (page pool)
        ↓
    BrowserTransport (Chrome CDP)

TopicManager owns the lifecycle. TopicRuntime owns the live state.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from egregore.providers.browser_manager import BrowserManager
from egregore.providers.cdp_transport import BrowserTransport
from egregore.synthesis.store import ResponseStore
from egregore.topic.events import TopicEventStore, TopicEventType
from egregore.topic.models import Topic
from egregore.topic.runtime import TopicRuntime, TopicState
from egregore.topic.store import TopicStore

logger = structlog.get_logger()


@dataclass
class SendResult:
    provider: str
    content: str
    success: bool
    latency_ms: float
    url: str = ""


class TopicManager:
    """Manages topic lifecycle. Creates TopicRuntime for live topics."""

    def __init__(
        self,
        transport: BrowserTransport,
        store: TopicStore,
        event_store: TopicEventStore,
        browser_manager: BrowserManager,
        response_store: ResponseStore | None = None,
    ) -> None:
        self._transport = transport
        self._store = store
        self._events = event_store
        self._browser_manager = browser_manager
        self._response_store = response_store
        self._runtimes: dict[str, TopicRuntime] = {}  # topic_id -> runtime

    async def create(self, title: str, providers: list[str]) -> Topic:
        """Create a topic and open pages."""
        topic = Topic(title=title, providers=providers)

        # Set base URLs for each provider
        for provider in providers:
            topic.set_url(provider, self._provider_url(provider))

        self._store.save(topic)

        # Create runtime and open pages
        runtime = TopicRuntime(topic, self._browser_manager, self._events)
        await runtime.open_pages()
        self._runtimes[topic.id] = runtime

        # Save again with actual conversation URLs
        self._store.save(topic)

        self._events.record(topic.id, TopicEventType.CREATED, detail=title)
        logger.info("topic_created", topic=topic.id, title=title, providers=providers)
        return topic

    async def send(self, topic_id: str, prompt: str, timeout_ms: int = 60000) -> list[SendResult]:
        """Send a prompt to all providers in a topic."""
        runtime = self._get_runtime(topic_id)
        runtime.touch()
        self._events.record(topic_id, TopicEventType.SENT, detail=prompt[:100])

        results = []
        for provider in runtime.topic.providers:
            page = await runtime.get_page(provider)
            if not page:
                results.append(SendResult(provider=provider, content="", success=False, latency_ms=0))
                continue

            url = runtime.topic.get_url(provider) or ""
            try:
                response = await self._transport.send(url, prompt, timeout_ms)
                results.append(SendResult(
                    provider=provider,
                    content=response.content,
                    success=response.success,
                    latency_ms=response.latency_ms,
                    url=url,
                ))
                if not response.success:
                    self._events.record(topic_id, TopicEventType.PROVIDER_FAILED, provider, response.error or "")
            except Exception as e:
                results.append(SendResult(provider=provider, content="", success=False, latency_ms=0, url=url))
                self._events.record(topic_id, TopicEventType.PROVIDER_FAILED, provider, str(e))

        # Save raw responses for future synthesis
        if self._response_store:
            response_dict = {r.provider: r.content for r in results if r.success}
            if response_dict:
                self._response_store.save(topic_id, prompt, response_dict)

        return results

    async def close(self, topic_id: str) -> None:
        """Close topic pages. Keep metadata."""
        runtime = self._runtimes.pop(topic_id, None)
        if runtime:
            await runtime.close_pages()
        self._events.record(topic_id, TopicEventType.CLOSED)
        logger.info("topic_closed", topic=topic_id)

    async def reopen(self, topic_id: str) -> Topic:
        """Reopen a topic from saved metadata."""
        topic = self._store.get(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        runtime = TopicRuntime(topic, self._browser_manager, self._events)
        runtime.metrics.reopen_count = 1
        await runtime.open_pages()
        self._runtimes[topic_id] = runtime

        self._events.record(topic_id, TopicEventType.REOPENED)
        logger.info("topic_reopened", topic=topic_id)
        return topic

    def list_topics(self) -> list[Topic]:
        return self._store.list_all()

    def delete_topic(self, topic_id: str) -> None:
        self._runtimes.pop(topic_id, None)
        self._store.delete(topic_id)

    def get_topic_stats(self, topic_id: str) -> dict:
        runtime = self._runtimes.get(topic_id)
        if runtime:
            return {
                "state": runtime.state.value,
                "open_count": runtime.metrics.open_count,
                "reopen_count": runtime.metrics.reopen_count,
                "page_create_count": runtime.metrics.page_create_count,
                "page_reuse_count": runtime.metrics.page_reuse_count,
                "provider_failure_count": runtime.metrics.provider_failure_count,
                "provider_recovery_count": runtime.metrics.provider_recovery_count,
                "send_count": runtime.metrics.send_count,
            }
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

    def _get_runtime(self, topic_id: str) -> TopicRuntime:
        runtime = self._runtimes.get(topic_id)
        if not runtime:
            raise ValueError(f"Topic {topic_id} not open. Call create() or reopen() first.")
        return runtime
