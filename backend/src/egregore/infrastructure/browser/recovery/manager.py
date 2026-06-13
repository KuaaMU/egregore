"""Recovery Manager — automatic recovery when providers fail.

Failures are normal. Recovery is a feature.

The recovery manager implements an escalation strategy:
1. Page refresh (cheapest)
2. Reopen page (moderate)
3. Recreate context (expensive)
4. Restart browser (nuclear option)

Each level is tried before escalating. The manager tracks
recovery attempts and gives up after max retries.

Pattern: Strategy / Escalation Chain
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum

import structlog

from egregore.domain.events.bus import Event, EventBus, EventType
from egregore.domain.health.types import HealthStatus, ProviderHealth
from egregore.domain.session.types import SessionState
from egregore.infrastructure.browser.sessions.manager import SessionManager
from egregore.infrastructure.browser.runtime.chromium import ChromiumRuntime

logger = structlog.get_logger()


class RecoveryLevel(str, Enum):
    """Recovery escalation levels.

    Each level is progressively more expensive but more likely to fix the issue.
    """

    REFRESH = "refresh"  # Reload the page
    REOPEN = "reopen"  # Close and reopen page
    RECREATE = "recreate"  # Destroy and recreate context
    RESTART = "restart"  # Restart the entire browser


class RecoveryResult:
    """Result of a recovery attempt."""

    def __init__(
        self,
        provider_id: str,
        level: RecoveryLevel,
        success: bool,
        error: str | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.level = level
        self.success = success
        self.error = error
        self.timestamp = datetime.now(timezone.utc)


class RecoveryManager:
    """Manages automatic recovery for failed providers.

    Usage:
        recovery = RecoveryManager(session_manager, runtime, event_bus)
        result = await recovery.recover("chatgpt")
    """

    def __init__(
        self,
        session_manager: SessionManager,
        runtime: ChromiumRuntime,
        event_bus: EventBus,
        max_retries: int = 3,
    ) -> None:
        self._session_manager = session_manager
        self._runtime = runtime
        self._bus = event_bus
        self._max_retries = max_retries
        self._recovery_counts: dict[str, int] = {}

    async def recover(self, provider_id: str) -> RecoveryResult:
        """Attempt recovery for a failed provider.

        Tries each recovery level in order until one succeeds.
        Returns the result of the last attempt.
        """
        # Check retry limit
        count = self._recovery_counts.get(provider_id, 0)
        if count >= self._max_retries:
            logger.error(
                "recovery_max_retries",
                provider_id=provider_id,
                max_retries=self._max_retries,
            )
            return RecoveryResult(
                provider_id=provider_id,
                level=RecoveryLevel.RESTART,
                success=False,
                error="Max retries exceeded",
            )

        self._recovery_counts[provider_id] = count + 1

        # Try each level
        for level in RecoveryLevel:
            result = await self._try_recovery(provider_id, level)
            if result.success:
                self._recovery_counts[provider_id] = 0  # Reset on success
                logger.info(
                    "recovery_succeeded",
                    provider_id=provider_id,
                    level=level,
                )
                return result

        # All levels failed
        logger.error("recovery_failed", provider_id=provider_id)
        return RecoveryResult(
            provider_id=provider_id,
            level=RecoveryLevel.RESTART,
            success=False,
            error="All recovery levels failed",
        )

    async def _try_recovery(
        self, provider_id: str, level: RecoveryLevel
    ) -> RecoveryResult:
        """Try a specific recovery level."""
        try:
            match level:
                case RecoveryLevel.REFRESH:
                    await self._refresh(provider_id)
                case RecoveryLevel.REOPEN:
                    await self._reopen(provider_id)
                case RecoveryLevel.RECREATE:
                    await self._recreate(provider_id)
                case RecoveryLevel.RESTART:
                    await self._restart(provider_id)

            return RecoveryResult(
                provider_id=provider_id,
                level=level,
                success=True,
            )
        except Exception as e:
            logger.warning(
                "recovery_level_failed",
                provider_id=provider_id,
                level=level,
                error=str(e),
            )
            return RecoveryResult(
                provider_id=provider_id,
                level=level,
                success=False,
                error=str(e),
            )

    async def _refresh(self, provider_id: str) -> None:
        """Level 1: Refresh the page."""
        session = await self._session_manager.get(provider_id)
        if session and session.page:
            await session.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

    async def _reopen(self, provider_id: str) -> None:
        """Level 2: Close and reopen the page."""
        session = await self._session_manager.get(provider_id)
        if session:
            if session.page and not session.page.is_closed():
                await session.page.close()
            session.page = await session.context.new_page()
            await session.page.goto(
                f"https://chatgpt.com/",  # TODO: use provider-specific URL
                wait_until="domcontentloaded",
            )

    async def _recreate(self, provider_id: str) -> None:
        """Level 3: Destroy and recreate the browser context."""
        await self._session_manager.close(provider_id)
        await self._runtime.close_context(provider_id)
        # Re-creation happens lazily on next get_or_create

    async def _restart(self, provider_id: str) -> None:
        """Level 4: Nuclear option — restart the entire browser."""
        await self._session_manager.close_all()
        await self._runtime.close()
        await self._runtime.start()
