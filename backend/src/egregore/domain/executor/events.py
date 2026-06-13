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

    Lifecycle:
        STARTED → THINKING_STARTED → THINKING_TOKEN+ → THINKING_ENDED
                → ANSWER_STARTED → ANSWER_TOKEN+ → ANSWER_ENDED
                → COMPLETED

    Or with tool calls:
        STARTED → ANSWER_STARTED → ANSWER_TOKEN+
                → TOOL_CALL → TOOL_RESULT → ANSWER_TOKEN+
                → COMPLETED

    Error paths:
        STARTED → ERROR
        STARTED → CANCELLED
    """

    # Lifecycle
    STARTED = "stream.started"
    COMPLETED = "stream.completed"

    # Thinking (Claude, DeepSeek, etc.)
    THINKING_STARTED = "stream.thinking.started"
    THINKING_TOKEN = "stream.thinking.token"
    THINKING_ENDED = "stream.thinking.ended"

    # Answer
    ANSWER_STARTED = "stream.answer.started"
    ANSWER_TOKEN = "stream.answer.token"
    ANSWER_ENDED = "stream.answer.ended"

    # Legacy alias — prefer ANSWER_TOKEN
    TOKEN = "stream.token"

    # Tool calls (agent mode)
    TOOL_CALL = "stream.tool.call"
    TOOL_RESULT = "stream.tool.result"

    # Error / Control
    ERROR = "stream.error"
    TIMEOUT = "stream.timeout"
    CANCELLED = "stream.cancelled"


class StreamEvent(BaseModel):
    """A single event in a response stream.

    Immutable. Emitted by executors, consumed by orchestrators,
    event bus, UI, and future consensus engine.

    Fields:
        type: What happened
        provider_id: Which provider emitted this
        content: For TOKEN events: the token text
        full_text: For COMPLETED: the full accumulated text
        phase: "thinking" or "answer" — for UI rendering
        error: For ERROR events: what went wrong
        metadata: Arbitrary extra data (tool name, model, etc.)
    """

    model_config = {"frozen": True}

    type: StreamEventType
    provider_id: str
    content: str = ""
    full_text: str = ""
    phase: str = ""  # "thinking" or "answer"
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)

    @property
    def is_token(self) -> bool:
        return self.type in (
            StreamEventType.TOKEN,
            StreamEventType.ANSWER_TOKEN,
            StreamEventType.THINKING_TOKEN,
        )

    @property
    def is_thinking(self) -> bool:
        return self.type in (
            StreamEventType.THINKING_STARTED,
            StreamEventType.THINKING_TOKEN,
            StreamEventType.THINKING_ENDED,
        )

    @property
    def is_answer(self) -> bool:
        return self.type in (
            StreamEventType.ANSWER_STARTED,
            StreamEventType.ANSWER_TOKEN,
            StreamEventType.ANSWER_ENDED,
        )

    @property
    def is_complete(self) -> bool:
        return self.type == StreamEventType.COMPLETED

    @property
    def is_error(self) -> bool:
        return self.type in (
            StreamEventType.ERROR,
            StreamEventType.TIMEOUT,
            StreamEventType.CANCELLED,
        )
