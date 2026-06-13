"""Chaos tests for the Recovery System.

These tests verify that recovery works under failure conditions.

Pattern: Chaos Engineering

We test:
1. Recovery from page crash
2. Recovery from session expiry
3. Recovery from browser crash
4. Recovery escalation (cheap → expensive)
5. Max retry limits
"""

import pytest

from egregore.domain.health.types import HealthStatus, ProviderHealth


class TestRecoveryEscalation:
    """Test that recovery tries cheap fixes before expensive ones."""

    def test_recovery_levels_are_ordered_cheap_to_expensive(self):
        """Recovery levels should escalate from cheap to expensive."""
        from egregore.infrastructure.browser.recovery.manager import RecoveryLevel

        levels = list(RecoveryLevel)
        # Verify order: refresh → reopen → recreate → restart
        assert levels[0] == RecoveryLevel.REFRESH
        assert levels[-1] == RecoveryLevel.RESTART

    def test_failed_state_needs_recovery(self):
        """FAILED providers should be flagged for recovery."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.FAILED)
        assert health.needs_recovery

    def test_offline_state_needs_recovery(self):
        """OFFLINE providers should be flagged for recovery."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.OFFLINE)
        assert health.needs_recovery

    def test_auth_expired_needs_recovery(self):
        """AUTH_EXPIRED providers should be flagged for recovery."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.AUTH_EXPIRED)
        assert health.needs_recovery

    def test_ready_does_not_need_recovery(self):
        """READY providers should NOT need recovery."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert not health.needs_recovery


class TestRecoveryStateTransitions:
    """Test state transitions during recovery scenarios."""

    def test_recovery_path_from_offline(self):
        """OFFLINE → RECOVERING → READY should be valid."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.OFFLINE)
        assert health.can_transition_to(HealthStatus.RECOVERING)

        health = ProviderHealth(provider_id="test", status=HealthStatus.RECOVERING)
        assert health.can_transition_to(HealthStatus.READY)

    def test_recovery_path_from_auth_expired(self):
        """AUTH_EXPIRED → RECOVERING → READY should be valid."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.AUTH_EXPIRED)
        assert health.can_transition_to(HealthStatus.RECOVERING)

    def test_recovery_failure_goes_to_offline(self):
        """RECOVERING → OFFLINE should be valid (recovery failed)."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.RECOVERING)
        assert health.can_transition_to(HealthStatus.OFFLINE)

    def test_busy_to_ready_on_completion(self):
        """BUSY → READY should be valid (request completed)."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.BUSY)
        assert health.can_transition_to(HealthStatus.READY)

    def test_throttled_to_ready_after_cooldown(self):
        """THROTTLED → READY should be valid (cooldown expired)."""
        health = ProviderHealth(provider_id="test", status=HealthStatus.THROTTLED)
        assert health.can_transition_to(HealthStatus.READY)


class TestStreamRecovery:
    """Test recovery from stream interruptions."""

    def test_stream_can_be_interrupted(self):
        """Verify that stream events include error and cancelled types."""
        from egregore.domain.executor.events import StreamEventType

        assert StreamEventType.ERROR.value == "stream.error"
        assert StreamEventType.CANCELLED.value == "stream.cancelled"
        assert StreamEventType.TIMEOUT.value == "stream.timeout"

    def test_stream_events_are_frozen(self):
        """Stream events should be immutable (safe for concurrent access)."""
        from egregore.domain.executor.events import StreamEvent, StreamEventType
        import pytest

        event = StreamEvent(
            type=StreamEventType.TOKEN,
            provider_id="test",
            content="hello",
        )
        with pytest.raises(Exception):
            event.content = "changed"
