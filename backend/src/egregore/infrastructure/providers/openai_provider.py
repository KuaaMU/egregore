"""OpenAI Provider — infrastructure adapter for OpenAI-compatible APIs.

This adapter supports any OpenAI-compatible API, including:
- OpenAI (GPT-4o, GPT-4-turbo, etc.)
- OpenRouter
- Any vLLM / Ollama with OpenAI-compatible endpoints

Pattern: Adapter (Hexagonal Architecture)

The adapter translates between our domain model (Message) and
the OpenAI API format. This is the ONLY place that knows about
the openai SDK.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import structlog
from openai import AsyncOpenAI

from egregore.domain.entities.message import Message, MessageRole, ProviderMeta
from egregore.domain.providers.base import BaseProvider, ProviderConfig, ProviderError

logger = structlog.get_logger()


class OpenAIProvider(BaseProvider):
    """Adapter for OpenAI-compatible APIs.

    Maps our Message domain model to OpenAI's chat format.
    Handles errors and translates them to ProviderError.
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or None,
        )

    def _to_openai_messages(self, messages: list[Message]) -> list[dict]:
        """Convert domain messages to OpenAI format.

        This is the adapter pattern in action — translating between
        our domain model and the external API's expected format.
        """
        role_map = {
            MessageRole.USER: "user",
            MessageRole.SYSTEM: "system",
            MessageRole.ASSISTANT: "assistant",
            MessageRole.PROVIDER: "assistant",
        }
        return [
            {"role": role_map.get(m.role, "user"), "content": m.content}
            for m in messages
        ]

    async def complete(self, messages: list[Message]) -> Message:
        """Generate a complete response from OpenAI."""
        start = time.monotonic()

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=self._to_openai_messages(messages),
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )

            latency_ms = (time.monotonic() - start) * 1000
            content = response.choices[0].message.content or ""
            usage = response.usage

            return Message(
                role=MessageRole.PROVIDER,
                content=content,
                provider_meta=ProviderMeta(
                    provider_id=self.provider_id,
                    model=self.model,
                    latency_ms=latency_ms,
                    token_count=usage.total_tokens if usage else 0,
                    temperature=self._config.temperature,
                ),
                metadata={"provider_id": self.provider_id},
            )

        except Exception as e:
            raise ProviderError(
                provider_id=self.provider_id,
                message=f"OpenAI API error: {e}",
                retryable=True,
            ) from e

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a response token by token."""
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=self._to_openai_messages(messages),
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise ProviderError(
                provider_id=self.provider_id,
                message=f"OpenAI stream error: {e}",
                retryable=True,
            ) from e

    async def health_check(self) -> bool:
        """Check if the OpenAI API is reachable."""
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
