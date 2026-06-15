"""BrowserManager — manages browser pages, reuses tabs.

Key design: auto-reconnect on any browser error.
The browser connection can die at any time (user closes Chrome,
system sleeps, network changes). We handle this gracefully.
"""

from __future__ import annotations

import asyncio

import structlog
from playwright.async_api import Browser, Page, Playwright, async_playwright

logger = structlog.get_logger()

DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class BrowserManager:
    """Manages browser pages with auto-reconnect."""

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._pages: dict[str, Page] = {}
        self._connecting = False

    async def connect(self) -> None:
        """Connect to Chrome via CDP. Idempotent."""
        if self._connecting:
            # Wait for ongoing connection
            for _ in range(30):
                await asyncio.sleep(0.5)
                if self._browser:
                    return
            raise RuntimeError("Connection timeout")

        if self._browser:
            return

        self._connecting = True
        try:
            # Clean up old playwright
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
            self._pages.clear()
            logger.info("browser_connected", cdp_url=self._cdp_url)
        except Exception as e:
            self._browser = None
            raise RuntimeError(f"Cannot connect to Chrome: {e}") from e
        finally:
            self._connecting = False

    async def _ensure_browser(self) -> Browser:
        """Ensure browser is connected. Reconnect if needed."""
        if self._browser:
            try:
                # Quick health check
                _ = self._browser.contexts
                return self._browser
            except Exception:
                logger.info("browser_connection_lost")
                self._browser = None
                self._pages.clear()

        if not self._browser:
            await self.connect()

        return self._browser

    async def get_page(self, url: str) -> Page:
        """Get or create a page for the given URL."""
        browser = await self._ensure_browser()

        # Check cache
        cached = self._pages.get(url)
        if cached:
            try:
                if not cached.is_closed():
                    return cached
            except Exception:
                pass
            self._pages.pop(url, None)

        # Search existing tabs
        try:
            for context in browser.contexts:
                for page in context.pages:
                    try:
                        if url in page.url:
                            self._pages[url] = page
                            logger.info("page_reused", url=url)
                            return page
                    except Exception:
                        continue
        except Exception:
            # Browser died during search — reconnect
            await self.connect()
            browser = self._browser

        # Create new tab
        try:
            contexts = browser.contexts
            context = contexts[0] if contexts else await browser.new_context()
        except Exception:
            # Context creation failed — reconnect and retry
            await self.connect()
            browser = self._browser
            contexts = browser.contexts
            context = contexts[0] if contexts else await browser.new_context()

        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        self._pages[url] = page
        logger.info("page_created", url=url)
        return page

    async def close(self) -> None:
        """Disconnect. Does NOT close user's browser."""
        self._pages.clear()
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._browser = None
        logger.info("browser_disconnected")

    @property
    def is_connected(self) -> bool:
        return self._browser is not None

    @property
    def active_pages(self) -> list[str]:
        return [url for url, page in self._pages.items() if not page.is_closed()]
