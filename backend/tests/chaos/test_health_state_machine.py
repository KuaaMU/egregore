"""Chaos tests for the Health State Machine.

These tests verify that the health state machine correctly handles
all valid transitions AND rejects invalid ones.

Pattern: State Machine Testing

We test:
1. All valid transitions succeed
2. All invalid transitions are rejected
3. The state machine never gets stuck
4. Recovery paths always exist
"""

import pytest

from egregore.domain.health.types import (
    HealthStatus,
    ProviderHealth,
    VALID_TRANSITIONS,
)


class TestHealthStateMachineTransitions:
    """Test every valid and invalid transition."""

    def test_all_states_have_transitions_defined(self):
        """Every state must have at least one valid transition."""
        for status in HealthStatus:
            assert status in VALID_TRANSITIONS, f"Missing transitions for {status}"
            assert len(VALID_TRANSITIONS[status]) > 0, f"No transitions from {status}"

    def test_valid_transitions_succeed(self):
        """All defined transitions should be accepted."""
        for from_status, to_statuses in VALID_TRANSITIONS.items():
            for to_status in to_statuses:
                health = ProviderHealth(provider_id="test", status=from_status)
                assert health.can_transition_to(to_status), (
                    f"Transition {from_status} → {to_status} should be valid"
                )

    def test_invalid_transitions_rejected(self):
        """Transitions not in VALID_TRANSITIONS should be rejected."""
        for from_status in HealthStatus:
            for to_status in HealthStatus:
                health = ProviderHealth(provider_id="test", status=from_status)
                is_valid = health.can_transition_to(to_status)
                should_be_valid = to_status in VALID_TRANSITIONS.get(from_status, set())
                assert is_valid == should_be_valid, (
                    f"Transition {from_status} → {to_status}: "
                    f"expected {should_be_valid}, got {is_valid}"
                )

    def test_no_self_loops(self):
        """No state should transition to itself (except through recovery)."""
        for status in HealthStatus:
            assert status not in VALID_TRANSITIONS.get(status, set()), (
                f"Self-loop detected: {status} → {status}"
            )

    def test_recovery_always_possible(self):
        """Every non-READY state should have a path back to READY.

        This is critical: the system must never get permanently stuck.
        """
        for status in HealthStatus:
            if status == HealthStatus.READY:
                continue
            # BFS to find path to READY
            visited = set()
            queue = [status]
            found_ready = False
            while queue:
                current = queue.pop(0)
                if current == HealthStatus.READY:
                    found_ready = True
                    break
                if current in visited:
                    continue
                visited.add(current)
                queue.extend(VALID_TRANSITIONS.get(current, set()))
            assert found_ready, f"No recovery path from {status} to READY"

    def test_terminal_states(self):
        """FAILED should only transition to RECOVERING (forced recovery)."""
        assert VALID_TRANSITIONS[HealthStatus.FAILED] == {HealthStatus.RECOVERING}


class TestHealthStatusProperties:
    """Test the computed properties on ProviderHealth."""

    def test_ready_is_available(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        assert health.is_available
        assert not health.needs_recovery
        assert not health.should_wait

    def test_busy_is_available(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.BUSY)
        assert health.is_available
        assert health.is_busy

    def test_offline_not_available(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.OFFLINE)
        assert not health.is_available
        assert health.needs_recovery

    def test_throttled_should_wait(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.THROTTLED)
        assert not health.is_available
        assert health.should_wait

    def test_auth_expired_needs_recovery(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.AUTH_EXPIRED)
        assert health.needs_recovery

    def test_display_format(self):
        health = ProviderHealth(
            provider_id="test",
            status=HealthStatus.READY,
            success_rate=0.98,
            latency_ms=120.0,
            total_requests=100,
        )
        display = health.display
        assert "🟢" in display
        assert "98%" in display
        assert "120ms" in display

    def test_display_no_data(self):
        health = ProviderHealth(provider_id="test", status=HealthStatus.READY)
        display = health.display
        assert "🟢" in display
        assert "—" in display  # No data yet

    def test_emoji_for_all_states(self):
        """Every status should have an emoji."""
        for status in HealthStatus:
            assert len(status.emoji) > 0
