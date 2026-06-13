"""Browser Transport — concrete transport using Playwright browser automation.

This is the bridge between the domain (BaseTransport) and the
browser infrastructure (Session, LocatorResolver, etc.).

Pattern: Adapter (Hexagonal Architecture)

The BrowserTransport:
1. Implements BaseTransport
2. Uses SessionManager to get/create sessions
3. Uses LocatorResolver to find UI elements
4. Yields StreamEvent objects as the response is generated

Each provider subclass (ChatGPTBrowserTransport, etc.) provides:
- The URL to navigate to
- The locators for that platform's UI
- The stream parsing logic
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import structlog
from playwright.async_api import Page

from egregore.domain.executor.events import StreamEvent, StreamEventType
from egregore.domain.executor.locator import LocatorChain
from egregore.domain.session.types import SessionState
from egregore.domain.transport.base import BaseTransport
from egregore.infrastructure.browser.locators.resolver import LocatorResolver
from egregore.infrastructure.browser.sessions.manager import Session, SessionManager

logger = structlog.get_logger()


class BrowserTransport(BaseTransport):
    """Browser-based transport using Playwright.

    This is the abstract base for all browser transports.
    Subclasses provide platform-specific locators and parsing.

    Lifecycle:
    1. Construct with SessionManager
    2. initialize() — creates session, navigates to URL
    3. send() — types prompt, waits for response, yields events
    4. health_check() — verifies page is functional
    5. close() — closes session
    """

    def __init__(
        self,
        session_manager: SessionManager,
        provider_id: str,
        base_url: str,
    ) -> None:
        self._session_manager = session_manager
        self._provider_id = provider_id
        self._base_url = base_url
        self._session: Session | None = None

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def is_ready(self) -> bool:
        return (
            self._session is not None
            and self._session.state in (SessionState.ACTIVE, SessionState.STREAMING)
        )

    async def initialize(self) -> None:
        """Create session and navigate to the provider's URL."""
        self._session = await self._session_manager.get_or_create(self._provider_id)
        page = await self._session.ensure_page()

        # Navigate if not already on the right page
        if self._base_url not in (page.url or ""):
            self._session.state = SessionState.CONNECTING
            await page.goto(self._base_url, wait_until="domcontentloaded")
            logger.info("navigated", provider_id=self._provider_id, url=self._base_url)

        # Wait for the page to be ready
        await self._on_page_ready(page)
        self._session.state = SessionState.ACTIVE

    async def send(self, prompt: str, system_prompt: str = "") -> AsyncIterator[StreamEvent]:
        """Send a prompt and yield response events.

        This is the core method. It:
        1. Ensures session is ready
        2. Types the prompt
        3. Clicks send
        4. Monitors the response for streaming tokens
        5. Yields StreamEvent objects

        Subclasses override _type_prompt, _click_send, _parse_stream
        for platform-specific behavior.
        """
        if self._session is None:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                provider_id=self._provider_id,
                error="Session not initialized",
            )
            return

        page = await self._session.ensure_page()
        resolver = LocatorResolver(page)

        try:
            self._session.state = SessionState.STREAMING

            # Emit: started
            yield StreamEvent(
                type=StreamEventType.STARTED,
                provider_id=self._provider_id,
            )

            # Type the prompt
            await self._type_prompt(resolver, prompt)
            await asyncio.sleep(0.3)  # Brief pause for UI to update

            # Click send
            await self._click_send(resolver)

            # Monitor response stream
            full_text = ""
            async for token in self._parse_stream(page, resolver):
                full_text += token
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    provider_id=self._provider_id,
                    content=token,
                )

            # Emit: completed
            yield StreamEvent(
                type=StreamEventType.COMPLETED,
                provider_id=self._provider_id,
                full_text=full_text,
            )

            self._session.state = SessionState.ACTIVE
            self._session.error_count = 0

        except Exception as e:
            self._session.error_count += 1
            self._session.state = SessionState.ACTIVE  # Recover to active
            yield StreamEvent(
                type=StreamEventType.ERROR,
                provider_id=self._provider_id,
                error=str(e),
            )

    async def health_check(self) -> bool:
        """Check if the session is functional."""
        if self._session is None:
            return False
        try:
            page = await self._session.ensure_page()
            return not page.is_closed()
        except Exception:
            return False

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None

    # === Platform-specific methods (override in subclasses) ===

    async def _on_page_ready(self, page: Page) -> None:
        """Called after navigation. Wait for the page to be interactive.

        Override in subclasses to wait for platform-specific elements.
        """
        await page.wait_for_load_state("networkidle")

    async def _type_prompt(self, resolver: LocatorResolver, prompt: str) -> None:
        """Type the prompt into the chat input.

        Override in subclasses for platform-specific input behavior.
        """
        raise NotImplementedError

    async def _click_send(self, resolver: LocatorResolver) -> None:
        """Click the send button.

        Override in subclasses for platform-specific send behavior.
        """
        raise NotImplementedError

    async def _parse_stream(
        self, page: Page, resolver: LocatorResolver
    ) -> AsyncIterator[str]:
        """Parse the streaming response and yield tokens.

        Override in subclasses for platform-specific stream parsing.
        """
        raise NotImplementedError
        yield ""  # Make this a generator
