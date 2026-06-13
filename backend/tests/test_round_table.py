"""Tests for the round table orchestrator.

Pattern: Unit Test with Mock Dependencies

We test the orchestrator using mock providers. This verifies the
orchestration logic without hitting real APIs.
"""

import pytest

from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.domain.events.bus import EventBus
from egregore.domain.providers.base import ProviderConfig
from egregore.domain.providers.registry import ProviderRegistry
from egregore.infrastructure.providers.mock import MockProvider


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def registry() -> ProviderRegistry:
    return ProviderRegistry()


@pytest.fixture
def orchestrator(event_bus: EventBus, registry: ProviderRegistry) -> RoundTableOrchestrator:
    return RoundTableOrchestrator(registry=registry, event_bus=event_bus)


@pytest.mark.asyncio
async def test_round_table_returns_all_responses(orchestrator, registry):
    """The orchestrator should collect responses from all providers."""
    for i in range(3):
        registry.register(
            MockProvider(
                config=ProviderConfig(provider_id=f"mock-{i}", model=f"model-{i}"),
                response=f"Response from mock-{i}",
            )
        )

    result = await orchestrator.execute("What is 2+2?")

    assert len(result.results) == 3
    assert all(r.success for r in result.results)
    assert result.prompt == "What is 2+2?"


@pytest.mark.asyncio
async def test_round_table_handles_provider_failure(orchestrator, registry):
    """A failing provider should not prevent others from responding."""

    class FailingProvider(MockProvider):
        async def complete(self, messages):
            raise RuntimeError("API is down")

    registry.register(
        MockProvider(
            config=ProviderConfig(provider_id="good", model="good-model"),
            response="I work fine",
        )
    )
    registry.register(
        FailingProvider(
            config=ProviderConfig(provider_id="bad", model="bad-model"),
        )
    )

    result = await orchestrator.execute("Test")

    assert len(result.results) == 2
    assert len(result.successful) == 1
    assert len(result.failed) == 1
    assert result.successful[0].provider_id == "good"
    assert result.failed[0].provider_id == "bad"


@pytest.mark.asyncio
async def test_round_table_emits_events(orchestrator, registry):
    """The orchestrator should emit events at each stage."""
    events = []

    async def collector(event):
        events.append(event)

    from egregore.domain.events.bus import EventType

    orchestrator._bus.on(EventType.PROMPT_RECEIVED, collector)
    orchestrator._bus.on(EventType.PROVIDER_DISPATCHED, collector)
    orchestrator._bus.on(EventType.PROVIDER_COMPLETED, collector)

    registry.register(
        MockProvider(
            config=ProviderConfig(provider_id="mock", model="mock-model"),
            response="Hello",
        )
    )

    await orchestrator.execute("Test")

    event_types = [e.type for e in events]
    assert EventType.PROMPT_RECEIVED in event_types
    assert EventType.PROVIDER_DISPATCHED in event_types
    assert EventType.PROVIDER_COMPLETED in event_types
