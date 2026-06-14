"""ChatGPT Provider — platform-specific logic only.

ChatGPTProvider doesn't know about CDP, Extension, or API.
It only knows about Transport.

Architecture:
    ChatGPTProvider → Transport → Platform

    Provider knows: URL, selectors, capabilities
    Transport knows: how to connect and communicate
"""

from __future__ import annotations

from egregore.providers.base import ProviderCapabilities, ProviderResponse, ProviderStatus
from egregore.providers.transport import Transport

CHATGPT_URL = "https://chatgpt.com/"


class ChatGPTProvider:
    """ChatGPT provider. Platform logic only, transport-agnostic."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._status = ProviderStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return "chatgpt"

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            models=["gpt-4o", "o3", "o4-mini", "gpt-4.1"],
            vision=True,
            file_upload=True,
            deep_research=True,
            thinking=True,
            web_search=True,
            canvas=True,
            image_generation=True,
            voice=True,
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
        response = await self._transport.send(CHATGPT_URL, prompt, timeout_ms)
        self._status = ProviderStatus.IDLE if response.success else ProviderStatus.BROKEN
        return ProviderResponse(
            content=response.content,
            model="gpt-4o",
            latency_ms=response.latency_ms,
            token_count=len(response.content.split()),
            success=response.success,
            error=response.error,
        )

    async def health(self) -> bool:
        return await self._transport.health(CHATGPT_URL)

    async def close(self) -> None:
        await self._transport.close()
        self._status = ProviderStatus.DISCONNECTED
