"""Chromium Runtime — manages the Playwright browser lifecycle.

This is the lowest layer of the browser stack. It owns:
- The Playwright instance
- Browser launch/teardown
- Persistent context creation

Design decisions:
- launch_persistent_context() — preserves cookies, localStorage, login state
- User data dirs are per-provider — each platform gets its own profile
- The runtime is a singleton — one browser engine for all providers
- Graceful shutdown — cleanup happens even on crashes

Pattern: Resource Manager / Singleton

Why persistent context over regular context?
- Login state survives across sessions (no re-login every time)
- Cookies persist
- localStorage/IndexedDB persist
- Extensions can be loaded
- This is how real users use browsers
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger()

# Default user data directory
DEFAULT_DATA_DIR = Path.home() / ".egregore" / "browser_data"


class ChromiumRuntime:
    """Manages the Playwright browser engine.

    Lifecycle:
    1. Construct with config
    2. Call start() — launches Playwright
    3. Call create_context() — creates persistent contexts
    4. Call close() — shuts everything down

    Thread safety: All methods are async. The runtime uses asyncio.Lock
    to prevent concurrent context creation.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        headless: bool = True,
        slow_mo: int = 0,
    ) -> None:
        self._data_dir = data_dir or DEFAULT_DATA_DIR
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright: Playwright | None = None
        self._lock = asyncio.Lock()
        self._contexts: dict[str, BrowserContext] = {}

    async def start(self) -> None:
        """Launch the Playwright engine.

        Must be called before creating contexts.
        Idempotent — safe to call multiple times.
        """
        if self._playwright is not None:
            return

        async with self._lock:
            if self._playwright is not None:
                return
            self._playwright = await async_playwright().start()
            logger.info("chromium_runtime_started", data_dir=str(self._data_dir))

    async def create_context(
        self,
        provider_id: str,
        viewport: dict | None = None,
        user_agent: str | None = None,
        locale: str = "en-US",
    ) -> BrowserContext:
        """Create a persistent browser context for a provider.

        Each provider gets its own persistent context with its own
        cookies, localStorage, and login state.

        Args:
            provider_id: Unique identifier for the provider
            viewport: Browser viewport size (default: 1280x800)
            user_agent: Custom user agent string
            locale: Browser locale

        Returns:
            A Playwright BrowserContext

        Raises:
            RuntimeError: If the runtime hasn't been started
        """
        if self._playwright is None:
            raise RuntimeError("Runtime not started. Call start() first.")

        async with self._lock:
            if provider_id in self._contexts:
                logger.info("context_reused", provider_id=provider_id)
                return self._contexts[provider_id]

            # Create provider-specific data directory
            provider_data_dir = self._data_dir / provider_id
            provider_data_dir.mkdir(parents=True, exist_ok=True)

            # Launch persistent context
            # This preserves cookies, localStorage, login state
            context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(provider_data_dir),
                headless=self._headless,
                slow_mo=self._slow_mo,
                viewport=viewport or {"width": 1280, "height": 800},
                user_agent=user_agent,
                locale=locale,
                # Anti-detection settings
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            self._contexts[provider_id] = context
            logger.info(
                "context_created",
                provider_id=provider_id,
                data_dir=str(provider_data_dir),
            )
            return context

    async def get_context(self, provider_id: str) -> BrowserContext | None:
        """Get an existing context for a provider."""
        return self._contexts.get(provider_id)

    async def close_context(self, provider_id: str) -> None:
        """Close a specific provider's context."""
        async with self._lock:
            context = self._contexts.pop(provider_id, None)
            if context:
                try:
                    await context.close()
                    logger.info("context_closed", provider_id=provider_id)
                except Exception as e:
                    logger.warning("context_close_error", provider_id=provider_id, error=str(e))

    async def close(self) -> None:
        """Shut down the runtime. Close all contexts.

        Idempotent. Safe to call even if some contexts are already closed.
        """
        async with self._lock:
            for provider_id in list(self._contexts.keys()):
                try:
                    await self._contexts[provider_id].close()
                except Exception:
                    pass
            self._contexts.clear()

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
                logger.info("chromium_runtime_stopped")

    @property
    def is_running(self) -> bool:
        return self._playwright is not None

    @property
    def active_contexts(self) -> list[str]:
        return list(self._contexts.keys())
