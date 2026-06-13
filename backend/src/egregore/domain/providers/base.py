"""Base provider — the port that all LLM adapters must implement.

This is the core of Hexagonal Architecture. The domain defines the interface;
infrastructure provides the implementations.

Why abstract base class over Protocol?
- ABC enforces implementation at instantiation time (fail fast)
- Clear documentation of required methods
- Easy to add shared logic via base class methods

Design tradeoff: We chose `complete()` + `stream()` as separate methods
rather than a single method with a `stream: bool` flag because:
1. Type safety — stream returns AsyncIterator, complete returns str
2. Explicit is better than implicit (Zen of Python)
3. Each can have optimized implementations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from egregore.domain.entities.message import Message


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a provider instance.

    Frozen to prevent mutation after construction.
    Each provider adapter maps this to its own config format.
    """

    provider_id: str
    model: str
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048


class BaseProvider(ABC):
    """The port — every LLM provider implements this interface.

    This is the most important abstraction in Egregore.
    It allows us to:
    - Add new providers without changing orchestrator code
    - Swap providers at runtime (hot-swappable)
    - Test orchestrators with mock providers
    - Route to different providers based on domain (V4)

    Lifecycle:
    1. Construct with ProviderConfig
    2. Call complete() or stream() as needed
    3. Provider handles its own error recovery
    """

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config

    @property
    def provider_id(self) -> str:
        return self._config.provider_id

    @property
    def model(self) -> str:
        return self._config.model

    @abstractmethod
    async def complete(self, messages: list[Message]) -> Message:
        """Generate a complete response (non-streaming).

        Args:
            messages: The conversation history.

        Returns:
            A Message with role=PROVIDER and provider_meta filled in.

        Raises:
            ProviderError: If the API call fails.
        """
        ...

    @abstractmethod
    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a response token by token.

        Args:
            messages: The conversation history.

        Yields:
            Text chunks as they arrive.

        Raises:
            ProviderError: If the API call fails.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this provider is available.

        Returns:
            True if the provider can accept requests.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.provider_id} model={self.model}>"


class ProviderError(Exception):
    """Raised when a provider fails to generate a response.

    Attributes:
        provider_id: Which provider failed.
        retryable: Whether the error is transient.
    """

    def __init__(self, provider_id: str, message: str, retryable: bool = False) -> None:
        self.provider_id = provider_id
        self.retryable = retryable
        super().__init__(f"[{provider_id}] {message}")
