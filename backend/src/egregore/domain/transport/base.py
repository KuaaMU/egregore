"""Base Transport — the port that decouples providers from transport mechanisms.

This is the key architectural insight from the refinement:

    Provider → Transport → Runtime → BrowserContext

The provider doesn't know if it's talking through a browser or an API.
The transport doesn't know which provider is using it.

This allows:
- BrowserTransport for web UI automation
- ApiTransport for direct API calls
- MockTransport for testing
- Future: WebSocketTransport, gRPCTransport

Pattern: Strategy / Port (Hexagonal Architecture)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from egregore.domain.executor.events import StreamEvent


class BaseTransport(ABC):
    """The transport port — providers interact with AI platforms through this.

    A transport is a channel to a single AI platform. It handles:
    - Sending prompts
    - Receiving responses (as event streams)
    - Health checking
    - Lifecycle management (init, close)

    Transports are long-lived. They maintain state (browser sessions,
    API connections) across multiple requests.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Which provider this transport connects to."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Set up the transport (launch browser, connect API, etc.).

        Called once at startup. Must be idempotent.
        """
        ...

    @abstractmethod
    async def send(self, prompt: str, system_prompt: str = "") -> AsyncIterator[StreamEvent]:
        """Send a prompt and receive a stream of events.

        This is the primary method. It returns an async generator
        that yields StreamEvent objects as the response is generated.

        Usage:
            async for event in transport.send("What is 2+2?"):
                if event.is_token:
                    print(event.content, end="")
                elif event.is_complete:
                    print(f"\nDone: {event.full_text}")
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this transport is operational.

        Returns True if the transport can accept requests.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Shut down the transport. Release resources.

        Called at application shutdown. Must be idempotent.
        """
        ...

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Is this transport ready to accept requests?"""
        ...
