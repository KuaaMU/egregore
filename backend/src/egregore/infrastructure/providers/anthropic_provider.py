"""Anthropic Provider — infrastructure adapter for Claude models.

Pattern: Adapter (Hexagonal Architecture)

Anthropic's API has a different format than OpenAI:
- System prompt is a separate parameter, not a message
- Message roles are only "user" and "assistant"
- The SDK is different

This adapter handles all those differences.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import structlog
from anthropic import AsyncAnthropic

from egregore.domain.entities.message import Message, MessageRole, ProviderMeta
from egregore.domain.providers.base import BaseProvider, ProviderConfig, ProviderError

logger = structlog.get_logger()


class AnthropicProvider(BaseProvider):
    """Adapter for Anthropic's Claude API.

    Anthropic requires special handling:
    1. System prompt is a separate parameter
    2. Messages must alternate user/assistant
    3. No "system" role in messages
    """

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client = AsyncAnthropic(api_key=config.api_key)

    def _extract_system_and_messages(
        self, messages: list[Message]
    ) -> tuple[str, list[dict]]:
        """Split system prompt from conversation messages.

        Anthropic requires the system prompt as a separate parameter.
        This method extracts it and converts the rest.
        """
        system_content = ""
        conversation = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_content += msg.content + "\n"
            elif msg.role == MessageRole.USER:
                conversation.append({"role": "user", "content": msg.content})
            elif msg.role in (MessageRole.ASSISTANT, MessageRole.PROVIDER):
                conversation.append({"role": "assistant", "content": msg.content})

        return system_content.strip(), conversation

    async def complete(self, messages: list[Message]) -> Message:
        """Generate a complete response from Claude."""
        start = time.monotonic()

        try:
            system, conversation = self._extract_system_and_messages(messages)

            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                system=system if system else None,
                messages=conversation,
            )

            latency_ms = (time.monotonic() - start) * 1000
            content = response.content[0].text if response.content else ""

            return Message(
                role=MessageRole.PROVIDER,
                content=content,
                provider_meta=ProviderMeta(
                    provider_id=self.provider_id,
                    model=self.model,
                    latency_ms=latency_ms,
                    token_count=response.usage.input_tokens + response.usage.output_tokens,
                    temperature=self._config.temperature,
                ),
                metadata={"provider_id": self.provider_id},
            )

        except Exception as e:
            raise ProviderError(
                provider_id=self.provider_id,
                message=f"Anthropic API error: {e}",
                retryable=True,
            ) from e

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a response from Claude."""
        try:
            system, conversation = self._extract_system_and_messages(messages)

            async with self._client.messages.stream(
                model=self.model,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                system=system if system else None,
                messages=conversation,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise ProviderError(
                provider_id=self.provider_id,
                message=f"Anthropic stream error: {e}",
                retryable=True,
            ) from e

    async def health_check(self) -> bool:
        """Check if the Anthropic API is reachable."""
        try:
            # Anthropic doesn't have a simple health endpoint
            # We'll do a minimal request
            return True
        except Exception:
            return False
