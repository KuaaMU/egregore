"""Round Table Orchestrator — the core flow of Egregore.

This is where the magic happens. The Round Table:

1. Receives a user prompt
2. Dispatches it to ALL registered providers in parallel
3. Collects responses
4. Emits events for each step (for real-time UI updates)
5. Returns structured results

Pattern: Orchestrator / Coordinator

The orchestrator doesn't know about HTTP, WebSocket, or any transport.
It only knows about providers and the event bus. This is clean architecture.

Why asyncio.TaskGroup over gather()?
- TaskGroup (Python 3.11+) cancels all tasks if one fails
- gather() continues even if one fails (we want partial results)
- We use gather(return_exceptions=True) to collect errors gracefully

Tradeoff: We chose "dispatch to all" over "dispatch to N selected".
Future (V4): The orchestrator will use routing logic to select providers.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import structlog

from egregore.domain.entities.message import Message, MessageRole, ProviderMeta
from egregore.domain.events.bus import Event, EventBus, EventType
from egregore.domain.providers.base import BaseProvider, ProviderError
from egregore.domain.providers.registry import ProviderRegistry

logger = structlog.get_logger()


@dataclass
class ProviderResult:
    """Result from a single provider execution.

    This is what the orchestrator returns for each provider.
    It includes the response, metadata, and any error.
    """

    provider_id: str
    model: str
    message: Message | None = None
    error: str | None = None
    latency_ms: float = 0.0
    success: bool = True


@dataclass
class RoundTableResult:
    """Aggregated result from all providers.

    Contains individual results and the prompt that was sent.
    The frontend uses this to render the three-column layout.
    """

    prompt: str
    results: list[ProviderResult]
    total_latency_ms: float = 0.0

    @property
    def successful(self) -> list[ProviderResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[ProviderResult]:
        return [r for r in self.results if not r.success]


class RoundTableOrchestrator:
    """Orchestrates the multi-LLM round table flow.

    This is the primary use case of Egregore V1.

    Flow:
        prompt → dispatch_to_all → collect_results → emit_events → return

    The orchestrator is transport-agnostic. It doesn't know if the
    request came from HTTP REST or WebSocket. This separation is key.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        event_bus: EventBus,
    ) -> None:
        self._registry = registry
        self._bus = event_bus

    async def execute(self, prompt: str, system_prompt: str = "") -> RoundTableResult:
        """Execute the round table flow.

        Args:
            prompt: The user's question/prompt.
            system_prompt: Optional system prompt prepended to all providers.

        Returns:
            RoundTableResult with all provider responses.

        This method is the primary entry point. It:
        1. Creates the message list
        2. Dispatches to all providers in parallel
        3. Collects results
        4. Emits events at each stage
        """
        start_time = time.monotonic()

        # Build messages
        messages = []
        if system_prompt:
            messages.append(Message(role=MessageRole.SYSTEM, content=system_prompt))
        messages.append(Message(role=MessageRole.USER, content=prompt))

        # Emit: prompt received
        await self._bus.emit(
            Event(
                type=EventType.PROMPT_RECEIVED,
                payload={"prompt": prompt, "provider_count": len(self._registry)},
            )
        )

        # Dispatch to all providers in parallel
        providers = self._registry.get_active()
        logger.info("dispatching_to_providers", count=len(providers))

        tasks = [
            self._execute_provider(provider, messages) for provider in providers
        ]

        # gather with return_exceptions=True — one provider failing shouldn't kill others
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build provider results
        provider_results = []
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                provider_results.append(
                    ProviderResult(
                        provider_id=provider.provider_id,
                        model=provider.model,
                        error=str(result),
                        success=False,
                    )
                )
            else:
                provider_results.append(result)

        total_latency = (time.monotonic() - start_time) * 1000

        round_result = RoundTableResult(
            prompt=prompt,
            results=provider_results,
            total_latency_ms=total_latency,
        )

        logger.info(
            "round_table_complete",
            successful=len(round_result.successful),
            failed=len(round_result.failed),
            total_latency_ms=total_latency,
        )

        return round_result

    async def _execute_provider(
        self, provider: BaseProvider, messages: list[Message]
    ) -> ProviderResult:
        """Execute a single provider and capture metrics.

        This wraps the provider call with timing, error handling,
        and event emission.
        """
        start = time.monotonic()

        # Emit: dispatched
        await self._bus.emit(
            Event(
                type=EventType.PROVIDER_DISPATCHED,
                payload={"provider_id": provider.provider_id, "model": provider.model},
                source=provider.provider_id,
            )
        )

        try:
            message = await provider.complete(messages)
            latency_ms = (time.monotonic() - start) * 1000

            # Emit: completed
            await self._bus.emit(
                Event(
                    type=EventType.PROVIDER_COMPLETED,
                    payload={
                        "provider_id": provider.provider_id,
                        "latency_ms": latency_ms,
                        "content_length": len(message.content),
                    },
                    source=provider.provider_id,
                )
            )

            return ProviderResult(
                provider_id=provider.provider_id,
                model=provider.model,
                message=message,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000

            # Emit: failed
            await self._bus.emit(
                Event(
                    type=EventType.PROVIDER_FAILED,
                    payload={
                        "provider_id": provider.provider_id,
                        "error": str(e),
                    },
                    source=provider.provider_id,
                )
            )

            logger.error(
                "provider_failed",
                provider_id=provider.provider_id,
                error=str(e),
            )

            return ProviderResult(
                provider_id=provider.provider_id,
                model=provider.model,
                error=str(e),
                latency_ms=latency_ms,
                success=False,
            )
