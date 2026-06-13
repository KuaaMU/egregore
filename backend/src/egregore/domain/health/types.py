"""Health types — domain model for provider health monitoring.

Health is a first-class concept, not an afterthought.
Every provider has a health status that drives routing decisions.

Pattern: State Machine

Health states form a directed graph with defined transitions.
The state machine prevents invalid transitions (e.g., FAILED → HEALTHY
must go through RECOVERING first).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Provider health state machine.

    Transitions:
        UNKNOWN → HEALTHY (first successful check)
        HEALTHY → DEGRADED (success rate < 90%)
        DEGRADED → HEALTHY (success rate >= 90%)
        DEGRADED → RECOVERING (3 consecutive failures)
        RECOVERING → HEALTHY (recovery succeeds)
        RECOVERING → FAILED (recovery fails 3x)
        FAILED → RECOVERING (manual trigger or periodic retry)
    """

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    EXPIRED = "expired"  # Login expired, needs re-auth
    FAILED = "failed"


# Valid state transitions — prevents illegal state changes
VALID_TRANSITIONS: dict[HealthStatus, set[HealthStatus]] = {
    HealthStatus.UNKNOWN: {HealthStatus.HEALTHY, HealthStatus.FAILED},
    HealthStatus.HEALTHY: {HealthStatus.DEGRADED, HealthStatus.EXPIRED, HealthStatus.FAILED},
    HealthStatus.DEGRADED: {HealthStatus.HEALTHY, HealthStatus.RECOVERING, HealthStatus.FAILED},
    HealthStatus.RECOVERING: {HealthStatus.HEALTHY, HealthStatus.FAILED},
    HealthStatus.EXPIRED: {HealthStatus.RECOVERING, HealthStatus.FAILED},
    HealthStatus.FAILED: {HealthStatus.RECOVERING},
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

    @property
    def is_available(self) -> bool:
        """Can this provider accept new requests?"""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    @property
    def needs_recovery(self) -> bool:
        """Should recovery be triggered?"""
        return self.status in (HealthStatus.EXPIRED, HealthStatus.FAILED)

    def can_transition_to(self, new_status: HealthStatus) -> bool:
        """Check if a state transition is valid."""
        return new_status in VALID_TRANSITIONS.get(self.status, set())


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
