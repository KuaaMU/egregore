"""Health Monitor — tracks provider health over time.

The health monitor is the system's immune system. It:
1. Periodically checks each provider's health
2. Maintains health state (state machine)
3. Triggers recovery when needed
4. Emits events for observability
5. Provides data for routing decisions (V3+)

Pattern: Observer / Monitor

The monitor doesn't fix problems — it detects them and triggers recovery.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import structlog

from egregore.domain.events.bus import Event, EventBus, EventType
from egregore.domain.health.types import (
    HealthCheckResult,
    HealthStatus,
    ProviderHealth,
    VALID_TRANSITIONS,
)
from egregore.domain.transport.base import BaseTransport

logger = structlog.get_logger()


class HealthMonitor:
    """Monitors provider health and maintains state.

    Usage:
        monitor = HealthMonitor(event_bus)
        monitor.register("chatgpt", chatgpt_transport)
        await monitor.start()  # Begins periodic checks
    """

    def __init__(
        self,
        event_bus: EventBus,
        check_interval_seconds: float = 60.0,
    ) -> None:
        self._bus = event_bus
        self._check_interval = check_interval_seconds
        self._transports: dict[str, BaseTransport] = {}
        self._health: dict[str, ProviderHealth] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def register(self, provider_id: str, transport: BaseTransport) -> None:
        """Register a provider for health monitoring."""
        self._transports[provider_id] = transport
        self._health[provider_id] = ProviderHealth(provider_id=provider_id)
        logger.info("health_monitor_registered", provider_id=provider_id)

    async def start(self) -> None:
        """Start periodic health checks."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("health_monitor_started", interval=self._check_interval)

    async def stop(self) -> None:
        """Stop periodic health checks."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("health_monitor_stopped")

    async def check_now(self, provider_id: str) -> ProviderHealth:
        """Run an immediate health check for a specific provider."""
        transport = self._transports.get(provider_id)
        if transport is None:
            return ProviderHealth(provider_id=provider_id, status=HealthStatus.UNKNOWN)

        result = await self._run_check(provider_id, transport)
        return self._update_health(result)

    def get_health(self, provider_id: str) -> ProviderHealth:
        """Get the current health status for a provider."""
        return self._health.get(
            provider_id,
            ProviderHealth(provider_id=provider_id, status=HealthStatus.UNKNOWN),
        )

    def get_all_health(self) -> dict[str, ProviderHealth]:
        """Get health status for all providers."""
        return dict(self._health)

    async def _check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                for provider_id, transport in self._transports.items():
                    try:
                        result = await self._run_check(provider_id, transport)
                        self._update_health(result)
                    except Exception as e:
                        logger.error(
                            "health_check_error",
                            provider_id=provider_id,
                            error=str(e),
                        )
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_loop_error", error=str(e))
                await asyncio.sleep(self._check_interval)

    async def _run_check(
        self, provider_id: str, transport: BaseTransport
    ) -> HealthCheckResult:
        """Run a single health check."""
        start = time.monotonic()
        try:
            ok = await transport.health_check()
            latency_ms = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                provider_id=provider_id,
                login_ok=ok,
                page_loaded=ok,
                input_available=ok,
                stream_ok=ok,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthCheckResult(
                provider_id=provider_id,
                latency_ms=latency_ms,
                error=str(e),
            )

    def _update_health(self, result: HealthCheckResult) -> ProviderHealth:
        """Update health state based on check result.

        Implements the health state machine:
        - Successful check → READY
        - Failed check → OFFLINE or RECOVERING
        - State transitions are validated against VALID_TRANSITIONS
        """
        current = self._health.get(result.provider_id)
        if current is None:
            current = ProviderHealth(provider_id=result.provider_id)
            self._health[result.provider_id] = current

        now = datetime.now(timezone.utc)

        if result.login_ok and result.stream_ok:
            # Success → READY
            new_status = HealthStatus.READY
            new_consecutive_failures = 0
            new_last_success = now
            new_last_failure = current.last_failure
            status_message = ""
        else:
            # Failure
            new_consecutive_failures = current.consecutive_failures + 1
            new_last_success = current.last_success
            new_last_failure = now

            # Determine new status based on error type
            if result.error and "auth" in result.error.lower():
                new_status = HealthStatus.AUTH_EXPIRED
                status_message = "Login session expired"
            elif result.error and "rate" in result.error.lower():
                new_status = HealthStatus.RATE_LIMITED
                status_message = "Rate limited by platform"
            elif new_consecutive_failures >= 5:
                new_status = HealthStatus.OFFLINE
                status_message = f"Offline after {new_consecutive_failures} failures"
            elif new_consecutive_failures >= 3:
                new_status = HealthStatus.RECOVERING
                status_message = "Attempting recovery"
            else:
                new_status = HealthStatus.OFFLINE
                status_message = result.error or "Health check failed"

        # Validate transition
        if not current.can_transition_to(new_status):
            logger.warning(
                "invalid_health_transition",
                provider_id=result.provider_id,
                from_status=current.status,
                to_status=new_status,
            )
            new_status = current.status
            status_message = current.status_message

        # Calculate success rate
        new_total = current.total_requests + 1
        new_failures = current.total_failures + (0 if result.login_ok else 1)
        success_rate = (new_total - new_failures) / new_total if new_total > 0 else 0.0

        updated = ProviderHealth(
            provider_id=result.provider_id,
            status=new_status,
            success_rate=success_rate,
            latency_ms=result.latency_ms,
            last_success=new_last_success,
            last_failure=new_last_failure,
            consecutive_failures=new_consecutive_failures,
            total_requests=new_total,
            total_failures=new_failures,
            status_message=status_message,
        )

        self._health[result.provider_id] = updated

        # Emit event if status changed
        if current.status != new_status:
            logger.info(
                "health_status_changed",
                provider_id=result.provider_id,
                from_status=current.status,
                to_status=new_status,
                message=status_message,
            )

        return updated
