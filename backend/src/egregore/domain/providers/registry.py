"""Provider Registry — manages the lifecycle of all providers.

Pattern: Registry / Service Locator

The registry knows about all available providers. The orchestrator
asks the registry for providers, not their concrete implementations.

This is dependency inversion: the orchestrator depends on the registry
abstraction, not on specific provider classes.

Tradeoff: Service Locator is sometimes considered an anti-pattern
because it hides dependencies. We mitigate this by:
1. Making the registry explicit (not a global singleton)
2. Requiring providers to be registered at startup
3. Using type hints everywhere
"""

from __future__ import annotations

from egregore.domain.providers.base import BaseProvider, ProviderError


class ProviderRegistry:
    """Manages registered providers.

    The registry is the single source of truth for which providers
    are available. It handles:
    - Registration
    - Lookup by ID
    - Health checks
    - Listing all active providers
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        """Register a provider.

        Raises ValueError if a provider with the same ID is already registered.
        This prevents accidental double-registration.
        """
        pid = provider.provider_id
        if pid in self._providers:
            raise ValueError(f"Provider '{pid}' is already registered")
        self._providers[pid] = provider

    def get(self, provider_id: str) -> BaseProvider:
        """Get a provider by ID.

        Raises ProviderError if not found.
        """
        if provider_id not in self._providers:
            raise ProviderError(
                provider_id=provider_id,
                message=f"Provider '{provider_id}' not found in registry",
            )
        return self._providers[provider_id]

    def get_all(self) -> list[BaseProvider]:
        """Get all registered providers."""
        return list(self._providers.values())

    def get_active(self) -> list[BaseProvider]:
        """Get all providers (future: filter by health status)."""
        return self.get_all()

    @property
    def provider_ids(self) -> list[str]:
        return list(self._providers.keys())

    def __len__(self) -> int:
        return len(self._providers)

    def __repr__(self) -> str:
        ids = ", ".join(self._providers.keys())
        return f"<ProviderRegistry providers=[{ids}]>"
