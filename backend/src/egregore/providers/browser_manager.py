"""BrowserManager — Persistent Context mode.

Default: headless Chrome with saved profile (silent).
Login: visible Chrome for one-time manual login.

Profile: ~/.egregore/profile/
Contains cookies, localStorage, login state for all platforms.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger()

DEFAULT_PROFILE_DIR = Path.home() / ".egregore" / "profile"


class BrowserManager:
    """Manages browser with persistent context."""

    def __init__(self, profile_dir: Path | None = None, headless: bool = True) -> None:
        self._profile_dir = profile_dir or DEFAULT_PROFILE_DIR
        self._headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._pages: dict[str, Page] = {}
        self._connecting = False

    async def connect(self) -> None:
        """Launch persistent context. Idempotent."""
        if self._connecting:
            for _ in range(30):
                await asyncio.sleep(0.5)
                if self._context:
                    return
            raise RuntimeError("Connection timeout")

        if self._context:
            return

        self._connecting = True
        try:
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass

            self._playwright = await async_playwright().start()
            self._profile_dir.mkdir(parents=True, exist_ok=True)

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=self._headless,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            self._pages.clear()
            logger.info("browser_connected", headless=self._headless, profile=str(self._profile_dir))
        except Exception as e:
            self._context = None
            raise RuntimeError(f"Cannot launch browser: {e}") from e
        finally:
            self._connecting = False

    async def _ensure_context(self) -> BrowserContext:
        if self._context:
            try:
                _ = self._context.pages
                return self._context
            except Exception:
                logger.info("context_lost_reconnecting")
                self._context = None
                self._pages.clear()

        await self.connect()
        return self._context

    async def get_page(self, url: str) -> Page:
        """Get or create a page for the given URL."""
        context = await self._ensure_context()

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
            for page in context.pages:
                try:
                    if url in page.url:
                        self._pages[url] = page
                        logger.info("page_reused", url=url)
                        return page
                except Exception:
                    continue
        except Exception:
            await self.connect()
            context = self._context

        # Create new tab
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            self._pages[url] = page
            logger.info("page_created", url=url)
            return page
        except Exception:
            await self.connect()
            context = self._context
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            self._pages[url] = page
            return page

    async def close(self) -> None:
        """Close browser. Profile is preserved."""
        self._pages.clear()
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("browser_disconnected")

    @property
    def is_connected(self) -> bool:
        return self._context is not None

    @property
    def profile_dir(self) -> Path:
        return self._profile_dir
