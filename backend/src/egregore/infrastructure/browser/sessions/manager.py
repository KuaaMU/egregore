"""Session Manager — manages long-lived browser sessions.

Each provider gets a Session object that wraps a BrowserContext + Page.
The session manager handles:
- Creating sessions
- Restoring sessions after restart (persistent context handles this)
- Tracking session state
- Closing sessions

Pattern: Manager / Factory

Why sessions exist:
- Browser contexts are expensive (200-500MB RAM each)
- Login state must persist across requests
- Pages should be reused when possible
- Session state drives health monitoring
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
from playwright.async_api import BrowserContext, Page

from egregore.domain.session.types import SessionInfo, SessionState
from egregore.infrastructure.browser.runtime.chromium import ChromiumRuntime

logger = structlog.get_logger()


@dataclass
class Session:
    """A long-lived browser session for a single provider.

    This is NOT a request-scoped object. It persists across requests.
    The underlying BrowserContext and Page are reused.

    Fields:
        provider_id: Which provider this session is for
        context: The Playwright BrowserContext
        page: The active page (created on first use)
        state: Current session state (state machine)
        created_at: When this session was created
        last_activity: Last time this session was used
        error_count: Number of errors since last success
    """

    provider_id: str
    context: BrowserContext
    page: Page | None = None
    state: SessionState = SessionState.IDLE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_count: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def info(self) -> SessionInfo:
        """Get an immutable snapshot of session state."""
        return SessionInfo(
            provider_id=self.provider_id,
            state=self.state,
            url=self.page.url if self.page else "",
            login_ok=self.state in (SessionState.ACTIVE, SessionState.STREAMING),
            last_activity=self.last_activity,
            error_count=self.error_count,
            uptime_seconds=(datetime.now(timezone.utc) - self.created_at).total_seconds(),
        )

    async def ensure_page(self) -> Page:
        """Ensure a page exists. Create one if needed."""
        if self.page is None or self.page.is_closed():
            self.page = await self.context.new_page()
            logger.info("page_created", provider_id=self.provider_id)
        return self.page

    async def close(self) -> None:
        """Close this session."""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        self.state = SessionState.CLOSED


class SessionManager:
    """Manages all browser sessions.

    One session per provider. Sessions are created lazily
    and reused across requests.

    Usage:
        manager = SessionManager(runtime)
        session = await manager.get_or_create("chatgpt")
        page = await session.ensure_page()
    """

    def __init__(self, runtime: ChromiumRuntime) -> None:
        self._runtime = runtime
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, provider_id: str) -> Session:
        """Get an existing session or create a new one.

        This is the primary method. It's idempotent — calling it
        twice with the same provider_id returns the same session.
        """
        async with self._lock:
            session = self._sessions.get(provider_id)

            if session is not None and session.state != SessionState.CLOSED:
                session.last_activity = datetime.now(timezone.utc)
                return session

            # Create new session
            context = await self._runtime.create_context(provider_id)
            session = Session(provider_id=provider_id, context=context)
            self._sessions[provider_id] = session

            logger.info("session_created", provider_id=provider_id)
            return session

    async def get(self, provider_id: str) -> Session | None:
        """Get an existing session without creating one."""
        return self._sessions.get(provider_id)

    async def close(self, provider_id: str) -> None:
        """Close and remove a specific session."""
        async with self._lock:
            session = self._sessions.pop(provider_id, None)
            if session:
                await session.close()
                await self._runtime.close_context(provider_id)
                logger.info("session_closed", provider_id=provider_id)

    async def close_all(self) -> None:
        """Close all sessions."""
        async with self._lock:
            for session in self._sessions.values():
                await session.close()
            self._sessions.clear()
            logger.info("all_sessions_closed")

    @property
    def active_sessions(self) -> list[str]:
        return [
            pid
            for pid, s in self._sessions.items()
            if s.state not in (SessionState.CLOSED, SessionState.FAILED)
        ]

    def get_all_info(self) -> list[SessionInfo]:
        """Get info about all sessions."""
        return [s.info for s in self._sessions.values()]
