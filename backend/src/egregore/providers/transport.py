"""Transport — the abstraction layer between Provider and Platform.

Provider doesn't know if it's using CDP, Extension, or API.
Transport handles the actual communication.

Architecture:
    Provider → Transport → Platform

Implementations:
    CdpTransport      — connects to user's Chrome via CDP
    ExtensionTransport — communicates with browser extension (future)
    ApiTransport      — direct API calls (future)

Pattern: Strategy / Port

This is the most important abstraction in Egregore.
It allows us to:
- Compare CDP vs Extension vs API with real data
- Swap transports without changing providers
- Let reality decide which transport is best
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class TransportType(str, Enum):
    CDP = "cdp"
    EXTENSION = "extension"
    API = "api"
    PLAYWRIGHT = "playwright"


@dataclass(frozen=True)
class TransportResponse:
    """Response from a transport."""

    content: str = ""
    success: bool = True
    error: str | None = None
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class Transport(Protocol):
    """The transport interface.

    All transport implementations must implement this.
    """

    @property
    def transport_type(self) -> TransportType:
        """Which transport this is."""
        ...

    async def connect(self, **kwargs) -> None:
        """Initialize the transport."""
        ...

    async def send(self, url: str, prompt: str, timeout_ms: int = 60000) -> TransportResponse:
        """Send a prompt to a platform and wait for response.

        Args:
            url: The platform URL (e.g., "https://chatgpt.com/")
            prompt: The prompt text
            timeout_ms: Timeout in milliseconds
        """
        ...

    async def health(self, url: str) -> bool:
        """Check if the platform is accessible."""
        ...

    async def close(self) -> None:
        """Shut down the transport."""
        ...
