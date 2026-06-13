"""Mock Provider — for testing and development.

Every system needs a mock. This provider returns deterministic
responses without hitting any API. It's essential for:

- Unit testing the orchestrator
- Development without API keys
- CI/CD pipelines
- Demos

Pattern: Test Double / Mock

The mock simulates latency and token counting so tests
exercise the same code paths as production.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from egregore.domain.entities.message import Message, MessageRole, ProviderMeta
from egregore.domain.providers.base import BaseProvider, ProviderConfig


class MockProvider(BaseProvider):
    """A mock provider that returns canned responses.

    Simulates latency to test timing-sensitive code.
    """

    def __init__(
        self,
        config: ProviderConfig,
        response: str = "This is a mock response.",
        latency_ms: float = 100.0,
    ) -> None:
        super().__init__(config)
        self._response = response
        self._latency_ms = latency_ms

    async def complete(self, messages: list[Message]) -> Message:
        """Return a mock response after simulating latency."""
        await asyncio.sleep(self._latency_ms / 1000)

        return Message(
            role=MessageRole.PROVIDER,
            content=self._response,
            provider_meta=ProviderMeta(
                provider_id=self.provider_id,
                model=self.model,
                latency_ms=self._latency_ms,
                token_count=len(self._response.split()),
            ),
            metadata={"provider_id": self.provider_id},
        )

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Stream the mock response word by word."""
        words = self._response.split()
        for word in words:
            await asyncio.sleep(0.02)
            yield word + " "

    async def health_check(self) -> bool:
        return True
