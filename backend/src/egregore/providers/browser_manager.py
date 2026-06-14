"""BrowserManager — manages browser pages, reuses tabs.

Current problem: every send() opens a new tab.
Solution: BrowserManager maintains a page pool.

Architecture:
    BrowserManager
        ├── chatgpt_page → reuses same tab
        ├── grok_page → reuses same tab
        ├── kimi_page → reuses same tab
        ├── qwen_page → reuses same tab
        └── doubao_page → reuses same tab

The entire program lifecycle: no new tabs. Silent.
"""

from __future__ import annotations

import asyncio

import structlog
from playwright.async_api import Browser, Page, Playwright, async_playwright

logger = structlog.get_logger()

DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class BrowserManager:
    """Manages browser pages. Reuses tabs. Silent operation."""

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._pages: dict[str, Page] = {}  # url_pattern -> page

    async def connect(self) -> None:
        """Connect to Chrome via CDP."""
        if self._playwright is not None:
            return

        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
            logger.info("browser_manager_connected", cdp_url=self._cdp_url)
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect to Chrome at {self._cdp_url}. "
                f"Start Chrome with: --remote-debugging-port=9222"
            ) from e

    async def get_page(self, url: str) -> Page:
        """Get or create a page for the given URL.

        Reuses existing tab if URL matches. Creates new tab only if needed.
        """
        # Check cache
        if url in self._pages and not self._pages[url].is_closed():
            return self._pages[url]

        # Search existing tabs
        for context in self._browser.contexts:
            for page in context.pages:
                if url in page.url:
                    self._pages[url] = page
                    logger.info("page_reused", url=url)
                    return page

        # Create new tab (only when needed)
        context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        self._pages[url] = page
        logger.info("page_created", url=url)
        return page

    async def close(self) -> None:
        """Disconnect. Does NOT close user's browser."""
        self._pages.clear()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("browser_manager_disconnected")

    @property
    def is_connected(self) -> bool:
        return self._browser is not None

    @property
    def active_pages(self) -> list[str]:
        return [url for url, page in self._pages.items() if not page.is_closed()]
