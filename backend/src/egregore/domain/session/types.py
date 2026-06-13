"""Session types — the domain model for browser sessions.

A Session represents a long-lived connection to an AI platform.
It is NOT a single request — it's a worker that persists across requests.

Design decisions:
- Sessions are identified by provider_id (one session per provider)
- SessionState is a state machine, not a boolean
- Frozen for thread safety across async tasks
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    """State machine for session lifecycle.

    Transitions:
        IDLE → CONNECTING → ACTIVE → STREAMING → ACTIVE
        ACTIVE → EXPIRED → RECONNECTING → ACTIVE
        ACTIVE → FAILED → RECOVERING → ACTIVE
        * → CLOSED (terminal)
    """

    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    STREAMING = "streaming"
    EXPIRED = "expired"
    RECONNECTING = "reconnecting"
    RECOVERING = "recovering"
    FAILED = "failed"
    CLOSED = "closed"


class SessionInfo(BaseModel):
    """Immutable snapshot of session state.

    Used for health checks, UI display, and debugging.
    """

    model_config = {"frozen": True}

    provider_id: str
    state: SessionState
    url: str = ""
    login_ok: bool = False
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_count: int = 0
    recovery_count: int = 0
    uptime_seconds: float = 0.0
