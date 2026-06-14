"""Grok Provider — platform-specific logic only.

GrokProvider doesn't know about CDP, Extension, or API.
It only knows about Transport.
"""

from __future__ import annotations

from egregore.providers.base import ProviderCapabilities, ProviderResponse, ProviderStatus
from egregore.providers.transport import Transport

GROK_URL = "https://grok.com/"


class GrokProvider:
    """Grok provider. Platform logic only, transport-agnostic."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._status = ProviderStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return "grok"

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            models=["grok-3", "grok-3-mini"],
            vision=True,
            web_search=True,
            thinking=True,
        )

    async def connect(self) -> None:
        self._status = ProviderStatus.CONNECTING
        try:
            await self._transport.connect()
            self._status = ProviderStatus.IDLE
        except Exception as e:
            self._status = ProviderStatus.BROKEN
            raise

    async def send(self, prompt: str, timeout_ms: int = 60000) -> ProviderResponse:
        self._status = ProviderStatus.GENERATING
        response = await self._transport.send(GROK_URL, prompt, timeout_ms)
        self._status = ProviderStatus.IDLE if response.success else ProviderStatus.BROKEN
        return ProviderResponse(
            content=response.content,
            model="grok-3",
            latency_ms=response.latency_ms,
            token_count=len(response.content.split()),
            success=response.success,
            error=response.error,
        )

    async def health(self) -> bool:
        return await self._transport.health(GROK_URL)

    async def close(self) -> None:
        await self._transport.close()
        self._status = ProviderStatus.DISCONNECTED
