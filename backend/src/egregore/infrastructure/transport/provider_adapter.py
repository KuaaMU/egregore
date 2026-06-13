"""Browser Provider Adapter — bridges BrowserTransport to BaseProvider.

This is the critical integration point. The orchestrator expects
BaseProvider (complete/stream), but BrowserTransport yields StreamEvents.

This adapter translates between the two worlds:
- BrowserTransport.send() → StreamEvent generator
- BaseProvider.complete() → Message (collects all events)
- BaseProvider.stream() → AsyncIterator[str] (forwards tokens)

Pattern: Adapter / Anti-Corruption Layer
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import structlog

from egregore.domain.entities.message import Message, MessageRole, ProviderMeta
from egregore.domain.executor.events import StreamEventType
from egregore.domain.providers.base import BaseProvider, ProviderConfig, ProviderError
from egregore.infrastructure.transport.browser import BrowserTransport

logger = structlog.get_logger()


class BrowserProviderAdapter(BaseProvider):
    """Adapts BrowserTransport to the BaseProvider interface.

    This allows browser-based providers to be used in the round table
    orchestrator alongside API-based providers.

    The orchestrator doesn't know (or care) that this provider
    uses a browser instead of an API.
    """

    def __init__(self, transport: BrowserTransport, model: str = "browser") -> None:
        super().__init__(
            config=ProviderConfig(
                provider_id=transport.provider_id,
                model=model,
            )
        )
        self._transport = transport

    async def complete(self, messages: list[Message]) -> Message:
        """Collect the full response from the event stream.

        This converts the async generator pattern (send) into a
        single Message object, matching the BaseProvider interface.
        """
        start = time.monotonic()
        prompt = self._extract_prompt(messages)
        system_prompt = self._extract_system_prompt(messages)

        full_text = ""
        error = None

        async for event in self._transport.send(prompt, system_prompt):
            if event.is_token:
                full_text += event.content
            elif event.is_complete:
                full_text = event.full_text or full_text
            elif event.is_error:
                error = event.error
                break

        latency_ms = (time.monotonic() - start) * 1000

        if error:
            raise ProviderError(
                provider_id=self.provider_id,
                message=error,
                retryable=True,
            )

        return Message(
            role=MessageRole.PROVIDER,
            content=full_text,
            provider_meta=ProviderMeta(
                provider_id=self.provider_id,
                model=self._config.model,
                latency_ms=latency_ms,
                token_count=len(full_text.split()),
            ),
            metadata={"provider_id": self.provider_id, "transport": "browser"},
        )

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Forward tokens from the event stream.

        This converts StreamEvent.TOKEN events into plain strings,
        matching the BaseProvider.stream() interface.
        """
        prompt = self._extract_prompt(messages)
        system_prompt = self._extract_system_prompt(messages)

        async for event in self._transport.send(prompt, system_prompt):
            if event.is_token:
                yield event.content
            elif event.is_error:
                raise ProviderError(
                    provider_id=self.provider_id,
                    message=event.error or "Stream error",
                    retryable=True,
                )

    async def health_check(self) -> bool:
        """Delegate to the transport's health check."""
        return await self._transport.health_check()

    def _extract_prompt(self, messages: list[Message]) -> str:
        """Extract the user prompt from the message list."""
        for msg in reversed(messages):
            if msg.role == MessageRole.USER:
                return msg.content
        return ""

    def _extract_system_prompt(self, messages: list[Message]) -> str:
        """Extract the system prompt from the message list."""
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                return msg.content
        return ""
