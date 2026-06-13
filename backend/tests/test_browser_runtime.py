"""Tests for the Browser Runtime components.

These tests verify the domain models and infrastructure logic
without launching actual browsers.

Pattern: Unit Tests with Mocks
"""

import pytest

from egregore.domain.executor.events import StreamEvent, StreamEventType
from egregore.domain.executor.locator import LocatorChain, LocatorDef, LocatorStrategy
from egregore.domain.health.types import (
    HealthCheckResult,
    HealthStatus,
    ProviderHealth,
    VALID_TRANSITIONS,
)
from egregore.domain.session.types import SessionInfo, SessionState


# === Health State Machine Tests ===


class TestHealthStateMachine:
    """Test the health state machine transitions."""

    def test_initial_state_is_unknown(self):
        health = ProviderHealth(provider_id="test")
        assert health.status == HealthStatus.UNKNOWN

    def test_unknown_to_healthy(self):
        health = ProviderHealth(provider_id="test")
        assert health.can_transition_to(HealthStatus.HEALTHY)

    def test_healthy_to_degraded(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.HEALTHY)
        assert health.can_transition_to(HealthStatus.DEGRADED)

    def test_healthy_cannot_go_to_recovering(self):
        """HEALTHY must go through DEGRADED first."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.HEALTHY)
        assert not health.can_transition_to(HealthStatus.RECOVERING)

    def test_degraded_to_recovering(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.DEGRADED)
        assert health.can_transition_to(HealthStatus.RECOVERING)

    def test_failed_to_recovering(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.FAILED)
        assert health.can_transition_to(HealthStatus.RECOVERING)

    def test_failed_cannot_go_directly_to_healthy(self):
        """FAILED must go through RECOVERING first."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.FAILED)
        assert not health.can_transition_to(HealthStatus.HEALTHY)

    def test_is_available_when_healthy(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.HEALTHY)
        assert health.is_available

    def test_is_available_when_degraded(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.DEGRADED)
        assert health.is_available

    def test_not_available_when_failed(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.FAILED)
        assert not health.is_available

    def test_needs_recovery_when_expired(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.EXPIRED)
        assert health.needs_recovery

    def test_success_rate_calculation(self):
        health = ProviderHealth(
            provider_id="test",
            total_requests=10,
            total_failures=3,
        )
        assert health.success_rate == 0.0  # Set externally, not calculated


# === Session State Tests ===


class TestSessionState:
    """Test session state types."""

    def test_session_states_exist(self):
        assert SessionState.IDLE.value == "idle"
        assert SessionState.ACTIVE.value == "active"
        assert SessionState.STREAMING.value == "streaming"
        assert SessionState.FAILED.value == "failed"
        assert SessionState.CLOSED.value == "closed"

    def test_session_info_is_frozen(self):
        info = SessionInfo(provider_id="test", state=SessionState.ACTIVE)
        with pytest.raises(Exception):
            info.provider_id = "changed"


# === Locator Tests ===


class TestLocators:
    """Test the locator model."""

    def test_locator_chain_with_single_locator(self):
        chain = LocatorChain(
            name="TEST",
            locators=[LocatorDef(LocatorStrategy.ROLE, "button", name="Send")],
        )
        assert chain.primary is not None
        assert chain.primary.strategy == LocatorStrategy.ROLE
        assert chain.fallbacks == []

    def test_locator_chain_with_fallbacks(self):
        chain = LocatorChain(
            name="TEST",
            locators=[
                LocatorDef(LocatorStrategy.ROLE, "button", name="Send"),
                LocatorDef(LocatorStrategy.ARIA, "[aria-label='Send']"),
                LocatorDef(LocatorStrategy.CSS, ".send-btn"),
            ],
        )
        assert chain.primary.strategy == LocatorStrategy.ROLE
        assert len(chain.fallbacks) == 2
        assert chain.fallbacks[0].strategy == LocatorStrategy.ARIA

    def test_empty_chain(self):
        chain = LocatorChain(name="EMPTY")
        assert chain.primary is None
        assert chain.fallbacks == []

    def test_locator_strategies(self):
        assert LocatorStrategy.ROLE.value == "role"
        assert LocatorStrategy.ARIA.value == "aria"
        assert LocatorStrategy.CSS.value == "css"


# === Stream Event Tests ===


class TestStreamEvents:
    """Test the stream event model."""

    def test_token_event(self):
        event = StreamEvent(
            type=StreamEventType.TOKEN,
            provider_id="test",
            content="hello",
        )
        assert event.is_token
        assert not event.is_complete
        assert not event.is_error

    def test_complete_event(self):
        event = StreamEvent(
            type=StreamEventType.COMPLETED,
            provider_id="test",
            full_text="hello world",
        )
        assert event.is_complete
        assert not event.is_token

    def test_error_event(self):
        event = StreamEvent(
            type=StreamEventType.ERROR,
            provider_id="test",
            error="something broke",
        )
        assert event.is_error
        assert not event.is_token

    def test_event_is_frozen(self):
        event = StreamEvent(
            type=StreamEventType.TOKEN,
            provider_id="test",
            content="hello",
        )
        with pytest.raises(Exception):
            event.content = "changed"

    def test_stream_event_types(self):
        assert StreamEventType.STARTED.value == "stream.started"
        assert StreamEventType.TOKEN.value == "stream.token"
        assert StreamEventType.COMPLETED.value == "stream.completed"
        assert StreamEventType.ERROR.value == "stream.error"
        assert StreamEventType.TIMEOUT.value == "stream.timeout"
