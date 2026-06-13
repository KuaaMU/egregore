"""Health types — domain model for provider health monitoring.

Health is a first-class concept, not an afterthought.
Every provider has a health status that drives routing decisions.

The health model is a proper state machine, not a boolean.

Pattern: State Machine

UI visualization:
    ChatGPT   🟢 READY     98%  120ms
    Claude    🟡 BUSY       95%  200ms
    Gemini    🔴 OFFLINE     0%  —
    DeepSeek  🟠 THROTTLED  85%  500ms
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Provider health state machine.

    These states describe the provider's ability to accept requests.
    They are more granular than healthy/unhealthy.

    Transitions:
        UNKNOWN → READY (first successful interaction)
        READY ↔ BUSY (processing a request)
        READY → THROTTLED (rate limited by platform)
        READY → AUTH_EXPIRED (login session expired)
        READY → OFFLINE (connection lost)
        BUSY → READY (request completed)
        THROTTLED → READY (cooldown expired)
        AUTH_EXPIRED → RECOVERING (auto-recovery triggered)
        OFFLINE → RECOVERING (reconnection attempt)
        RECOVERING → READY (recovery succeeded)
        RECOVERING → OFFLINE (recovery failed)
    """

    UNKNOWN = "unknown"  # Initial state, never checked
    READY = "ready"  # Can accept requests
    BUSY = "busy"  # Currently processing a request
    THROTTLED = "throttled"  # Rate limited, wait before retry
    AUTH_EXPIRED = "auth_expired"  # Login session expired
    RATE_LIMITED = "rate_limited"  # Platform rate limit hit
    RECOVERING = "recovering"  # Attempting to recover
    OFFLINE = "offline"  # Cannot connect
    FAILED = "failed"  # Unrecoverable failure

    @property
    def emoji(self) -> str:
        """Human-readable status indicator."""
        return {
            HealthStatus.UNKNOWN: "⚪",
            HealthStatus.READY: "🟢",
            HealthStatus.BUSY: "🟡",
            HealthStatus.THROTTLED: "🟠",
            HealthStatus.AUTH_EXPIRED: "🔐",
            HealthStatus.RATE_LIMITED: "🟠",
            HealthStatus.RECOVERING: "🔄",
            HealthStatus.OFFLINE: "🔴",
            HealthStatus.FAILED: "❌",
        }.get(self, "⚪")


# Valid state transitions — prevents illegal state changes
VALID_TRANSITIONS: dict[HealthStatus, set[HealthStatus]] = {
    HealthStatus.UNKNOWN: {HealthStatus.READY, HealthStatus.OFFLINE, HealthStatus.FAILED},
    HealthStatus.READY: {
        HealthStatus.BUSY,
        HealthStatus.THROTTLED,
        HealthStatus.AUTH_EXPIRED,
        HealthStatus.RATE_LIMITED,
        HealthStatus.OFFLINE,
        HealthStatus.FAILED,
    },
    HealthStatus.BUSY: {
        HealthStatus.READY,
        HealthStatus.OFFLINE,
        HealthStatus.FAILED,
    },
    HealthStatus.THROTTLED: {
        HealthStatus.READY,
        HealthStatus.OFFLINE,
    },
    HealthStatus.AUTH_EXPIRED: {
        HealthStatus.RECOVERING,
        HealthStatus.FAILED,
    },
    HealthStatus.RATE_LIMITED: {
        HealthStatus.READY,
        HealthStatus.RECOVERING,
    },
    HealthStatus.RECOVERING: {
        HealthStatus.READY,
        HealthStatus.OFFLINE,
        HealthStatus.FAILED,
    },
    HealthStatus.OFFLINE: {
        HealthStatus.RECOVERING,
        HealthStatus.FAILED,
    },
    HealthStatus.FAILED: {
        HealthStatus.RECOVERING,
    },
}


class ProviderHealth(BaseModel):
    """Immutable snapshot of a provider's health.

    Used by:
    - Routing decisions (skip unhealthy providers)
    - UI dashboard (show status indicators)
    - Recovery system (trigger recovery when needed)
    """

    model_config = {"frozen": True}

    provider_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    success_rate: float = 0.0  # 0.0 to 1.0
    latency_ms: float = 0.0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    status_message: str = ""  # Human-readable status detail

    @property
    def is_available(self) -> bool:
        """Can this provider accept new requests?"""
        return self.status in (HealthStatus.READY, HealthStatus.BUSY)

    @property
    def is_busy(self) -> bool:
        """Is this provider currently processing?"""
        return self.status == HealthStatus.BUSY

    @property
    def needs_recovery(self) -> bool:
        """Should recovery be triggered?"""
        return self.status in (
            HealthStatus.AUTH_EXPIRED,
            HealthStatus.OFFLINE,
            HealthStatus.FAILED,
        )

    @property
    def should_wait(self) -> bool:
        """Should callers wait before sending requests?"""
        return self.status in (HealthStatus.THROTTLED, HealthStatus.RATE_LIMITED)

    def can_transition_to(self, new_status: HealthStatus) -> bool:
        """Check if a state transition is valid."""
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    @property
    def display(self) -> str:
        """Human-readable status for UI."""
        emoji = self.status.emoji
        rate = f"{self.success_rate:.0%}" if self.total_requests > 0 else "—"
        latency = f"{self.latency_ms:.0f}ms" if self.latency_ms > 0 else "—"
        return f"{emoji} {self.status.value} {rate} {latency}"


class HealthCheckResult(BaseModel):
    """Result of a single health check."""

    model_config = {"frozen": True}

    provider_id: str
    login_ok: bool = False
    page_loaded: bool = False
    input_available: bool = False
    stream_ok: bool = False
    latency_ms: float = 0.0
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
