"""Executor events — the domain model for event-driven streaming.

This is the most important design decision in the browser runtime.

Instead of:
    response = await executor.send_prompt(prompt)  # blocking

We do:
    async for event in executor.run(prompt):  # streaming
        match event.type:
            case StreamEventType.TOKEN: handle_token(event)
            case StreamEventType.DONE: handle_done(event)

Why?
1. Real-time UI updates — tokens appear as they're generated
2. Event bus integration — any subscriber can listen
3. Composability — consensus/debate can observe streams
4. Cancellation — caller can stop at any time
5. Timeout detection — if no tokens for N seconds, something is wrong

Pattern: Event Sourcing / Async Generator
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    """Types of events emitted during a stream.

    These form a lifecycle:
        STARTED → (TOKEN)+ → COMPLETED
        STARTED → ERROR
    """

    STARTED = "stream.started"
    TOKEN = "stream.token"
    COMPLETED = "stream.completed"
    ERROR = "stream.error"
    TIMEOUT = "stream.timeout"


class StreamEvent(BaseModel):
    """A single event in a response stream.

    Immutable. Emitted by executors, consumed by orchestrators,
    event bus, UI, and future consensus engine.
    """

    model_config = {"frozen": True}

    type: StreamEventType
    provider_id: str
    content: str = ""  # For TOKEN events: the token text
    full_text: str = ""  # For COMPLETED: the full accumulated text
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)

    @property
    def is_token(self) -> bool:
        return self.type == StreamEventType.TOKEN

    @property
    def is_complete(self) -> bool:
        return self.type == StreamEventType.COMPLETED

    @property
    def is_error(self) -> bool:
        return self.type in (StreamEventType.ERROR, StreamEventType.TIMEOUT)
