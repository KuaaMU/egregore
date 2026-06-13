"""Tests for the round table orchestrator."""

import pytest

from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.domain.events.bus import EventBus, EventType
from egregore.domain.providers.base import ProviderConfig
from egregore.domain.providers.registry import ProviderRegistry
from egregore.infrastructure.providers.mock import MockProvider


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def registry():
    return ProviderRegistry()


@pytest.fixture
def orchestrator(event_bus, registry):
    return RoundTableOrchestrator(registry=registry, event_bus=event_bus)


@pytest.mark.asyncio
async def test_round_table_returns_all_responses(orchestrator, registry):
    for i in range(3):
        registry.register(MockProvider(
            config=ProviderConfig(provider_id=f"mock-{i}", model=f"model-{i}"),
            response=f"Response from mock-{i}",
        ))
    result = await orchestrator.execute("What is 2+2?")
    assert len(result.results) == 3
    assert all(r.success for r in result.results)


@pytest.mark.asyncio
async def test_round_table_handles_provider_failure(orchestrator, registry):
    class FailingProvider(MockProvider):
        async def complete(self, messages):
            raise RuntimeError("API is down")

    registry.register(MockProvider(
        config=ProviderConfig(provider_id="good", model="good-model"),
        response="I work fine",
    ))
    registry.register(FailingProvider(
        config=ProviderConfig(provider_id="bad", model="bad-model"),
    ))
    result = await orchestrator.execute("Test")
    assert len(result.results) == 2
    assert len(result.successful) == 1
    assert len(result.failed) == 1


@pytest.mark.asyncio
async def test_round_table_emits_events(orchestrator, registry):
    events = []
    async def collector(event):
        events.append(event)

    orchestrator._bus.on(EventType.PROMPT_RECEIVED, collector)
    orchestrator._bus.on(EventType.PROVIDER_DISPATCHED, collector)
    orchestrator._bus.on(EventType.PROVIDER_COMPLETED, collector)

    registry.register(MockProvider(
        config=ProviderConfig(provider_id="mock", model="mock-model"),
        response="Hello",
    ))
    await orchestrator.execute("Test")

    event_types = [e.type for e in events]
    assert EventType.PROMPT_RECEIVED in event_types
    assert EventType.PROVIDER_DISPATCHED in event_types
    assert EventType.PROVIDER_COMPLETED in event_types
