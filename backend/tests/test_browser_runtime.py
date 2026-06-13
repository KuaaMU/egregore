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

    def test_unknown_to_ready(self):
        health = ProviderHealth(provider_id="test")
        assert health.can_transition_to(HealthStatus.READY)

    def test_ready_to_busy(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert health.can_transition_to(HealthStatus.BUSY)

    def test_ready_to_throttled(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert health.can_transition_to(HealthStatus.THROTTLED)

    def test_ready_to_auth_expired(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert health.can_transition_to(HealthStatus.AUTH_EXPIRED)

    def test_ready_to_offline(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert health.can_transition_to(HealthStatus.OFFLINE)

    def test_busy_to_ready(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.BUSY)
        assert health.can_transition_to(HealthStatus.READY)

    def test_throttled_to_ready(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.THROTTLED)
        assert health.can_transition_to(HealthStatus.READY)

    def test_auth_expired_to_recovering(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.AUTH_EXPIRED)
        assert health.can_transition_to(HealthStatus.RECOVERING)

    def test_offline_to_recovering(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.OFFLINE)
        assert health.can_transition_to(HealthStatus.RECOVERING)

    def test_recovering_to_ready(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.RECOVERING)
        assert health.can_transition_to(HealthStatus.READY)

    def test_failed_to_recovering(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.FAILED)
        assert health.can_transition_to(HealthStatus.RECOVERING)

    def test_is_available_when_ready(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert health.is_available

    def test_is_available_when_busy(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.BUSY)
        assert health.is_available

    def test_not_available_when_offline(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.OFFLINE)
        assert not health.is_available

    def test_needs_recovery_when_auth_expired(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.AUTH_EXPIRED)
        assert health.needs_recovery

    def test_should_wait_when_throttled(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.THROTTLED)
        assert health.should_wait

    def test_should_wait_when_rate_limited(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.RATE_LIMITED)
        assert health.should_wait


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
            type=StreamEventType.ANSWER_TOKEN,
            provider_id="test",
            content="hello",
        )
        assert event.is_token
        assert event.is_answer
        assert not event.is_thinking
        assert not event.is_complete
        assert not event.is_error

    def test_thinking_token_event(self):
        event = StreamEvent(
            type=StreamEventType.THINKING_TOKEN,
            provider_id="test",
            content="let me think...",
        )
        assert event.is_token
        assert event.is_thinking
        assert not event.is_answer

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

    def test_cancelled_event(self):
        event = StreamEvent(
            type=StreamEventType.CANCELLED,
            provider_id="test",
        )
        assert event.is_error

    def test_event_is_frozen(self):
        event = StreamEvent(
            type=StreamEventType.ANSWER_TOKEN,
            provider_id="test",
            content="hello",
        )
        with pytest.raises(Exception):
            event.content = "changed"

    def test_stream_event_types(self):
        assert StreamEventType.STARTED.value == "stream.started"
        assert StreamEventType.ANSWER_TOKEN.value == "stream.answer.token"
        assert StreamEventType.THINKING_TOKEN.value == "stream.thinking.token"
        assert StreamEventType.COMPLETED.value == "stream.completed"
        assert StreamEventType.ERROR.value == "stream.error"
        assert StreamEventType.CANCELLED.value == "stream.cancelled"
        assert StreamEventType.TOOL_CALL.value == "stream.tool.call"
        assert StreamEventType.TOOL_RESULT.value == "stream.tool.result"


# === Capabilities Tests ===


class TestCapabilities:
    """Test the capability model."""

    def test_chatgpt_capabilities(self):
        from egregore.domain.executor.capabilities import Capabilities

        caps = Capabilities.chatgpt()
        assert caps.streaming
        assert caps.vision
        assert caps.tool_use
        assert caps.web_search

    def test_claude_capabilities(self):
        from egregore.domain.executor.capabilities import Capabilities

        caps = Capabilities.claude()
        assert caps.streaming
        assert caps.thinking
        assert caps.vision
        assert caps.supports_continuation

    def test_mock_capabilities(self):
        from egregore.domain.executor.capabilities import Capabilities

        caps = Capabilities.mock()
        assert caps.streaming
        assert not caps.thinking
        assert not caps.vision

    def test_supports_method(self):
        from egregore.domain.executor.capabilities import Capabilities

        caps = Capabilities.claude()
        assert caps.supports("thinking")
        assert caps.supports("vision")
        assert not caps.supports("web_search")
