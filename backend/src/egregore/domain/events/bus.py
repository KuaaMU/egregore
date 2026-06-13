"""Event Bus — the nervous system of Egregore.

This is a simple in-process pub/sub event bus. It decouples
producers from consumers, enabling:

- Providers to emit events without knowing who listens
- The orchestrator to react to provider completions
- Future: WebSocket to push events to frontend
- Future: Event sourcing for replay/debugging

Why in-process now, distributed later?
- Start simple, evolve when needed
- In-process is fast and debuggable
- The interface stays the same when we move to Redis Streams / NATS

Pattern: Observer / Event Bus / Mediator
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of events flowing through the system.

    Each event type maps to a lifecycle stage of the round-table flow.
    """

    # Request lifecycle
    PROMPT_RECEIVED = "prompt.received"
    PROVIDER_DISPATCHED = "provider.dispatched"
    PROVIDER_STREAM_CHUNK = "provider.stream.chunk"
    PROVIDER_COMPLETED = "provider.completed"
    PROVIDER_FAILED = "provider.failed"

    # Consensus
    CONSENSUS_STARTED = "consensus.started"
    CONSENSUS_COMPLETED = "consensus.completed"

    # System
    SYSTEM_ERROR = "system.error"


@dataclass(frozen=True)
class Event:
    """An immutable event flowing through the bus.

    Events carry a type, payload, and metadata.
    They are the primary communication mechanism.
    """

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """In-process async event bus.

    Thread-safe via asyncio.Lock. Handlers are coroutines,
    so they can do async work (DB writes, API calls, etc.).

    Usage:
        bus = EventBus()
        bus.on(EventType.PROVIDER_COMPLETED, my_handler)
        await bus.emit(Event(type=EventType.PROVIDER_COMPLETED, payload={...}))
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._history: list[Event] = []  # For debugging; bounded in production

    def on(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type.

        Why not async? Registration is synchronous; only emission is async.
        This keeps setup code simple.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: EventHandler) -> None:
        """Unregister a handler."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers.

        Handlers run concurrently. If one fails, others still execute.
        Errors are collected but don't propagate — the bus is fire-and-forget.
        """
        self._history.append(event)

        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return

        async with self._lock:
            tasks = [asyncio.create_task(h(event)) for h in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                # Log but don't propagate — bus is best-effort
                import structlog

                logger = structlog.get_logger()
                logger.error("event_handler_failed", event=event.type, error=str(result))

    @property
    def history(self) -> list[Event]:
        return list(self._history)
