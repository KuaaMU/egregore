"""Unified Provider interface — the core abstraction of Egregore.

Every AI platform (ChatGPT, Grok, Kimi, Qwen, Doubao) implements
this interface. The rest of Egregore only talks to Provider.

Lifecycle:
    provider = ChatGPTProvider()
    await provider.connect()      # Attach to browser
    await provider.send("Hello")  # Send prompt
    await provider.health()       # Check status
    await provider.close()        # Disconnect

Pattern: Protocol / Interface

Why Protocol over ABC?
- Structural typing — no inheritance needed
- Easier to test with mocks
- More Pythonic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable


class ProviderStatus(str, Enum):
    """Provider lifecycle states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    GENERATING = "generating"
    RATE_LIMITED = "rate_limited"
    BROKEN = "broken"
    RECOVERING = "recovering"


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider can do."""

    models: list[str] = field(default_factory=list)
    vision: bool = False
    file_upload: bool = False
    deep_research: bool = False
    thinking: bool = False
    web_search: bool = False
    canvas: bool = False
    image_generation: bool = False
    voice: bool = False


@dataclass(frozen=True)
class ProviderResponse:
    """Response from a provider."""

    content: str = ""
    model: str = ""
    latency_ms: float = 0.0
    token_count: int = 0
    success: bool = True
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@runtime_checkable
class Provider(Protocol):
    """Unified provider interface.

    All platform connectors must implement this.
    """

    @property
    def name(self) -> str:
        """Provider name (e.g., 'chatgpt', 'grok', 'kimi')."""
        ...

    @property
    def status(self) -> ProviderStatus:
        """Current lifecycle status."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """What this provider can do."""
        ...

    async def connect(self) -> None:
        """Attach to the platform (browser CDP, API, etc.)."""
        ...

    async def send(self, prompt: str, timeout_ms: int = 60000) -> ProviderResponse:
        """Send a prompt and wait for response."""
        ...

    async def health(self) -> bool:
        """Check if the provider is operational."""
        ...

    async def close(self) -> None:
        """Disconnect. Release resources."""
        ...
