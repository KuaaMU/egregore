"""CdpTransport — connects to user's Chrome via CDP.

This is the first Transport implementation.
It attaches to the user's running Chrome instance.

Usage:
    transport = CdpTransport()
    await transport.connect()
    response = await transport.send("https://chatgpt.com/", "Hello")
"""

from __future__ import annotations

import asyncio
import time

import structlog
from playwright.async_api import Page, Playwright, async_playwright

from egregore.providers.transport import TransportResponse, TransportType

logger = structlog.get_logger()

DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class CdpTransport:
    """Transport via Chrome DevTools Protocol.

    Attaches to user's running Chrome. Silent, no popup.
    """

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._pages: dict[str, Page] = {}  # url -> page

    @property
    def transport_type(self) -> TransportType:
        return TransportType.CDP

    async def connect(self, **kwargs) -> None:
        """Connect to Chrome via CDP."""
        if self._playwright is not None:
            return

        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
            logger.info("cdp_connected", cdp_url=self._cdp_url)
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect to Chrome at {self._cdp_url}. "
                f"Start Chrome with: --remote-debugging-port=9222"
            ) from e

    async def send(self, url: str, prompt: str, timeout_ms: int = 60000) -> TransportResponse:
        """Send prompt to a platform and wait for response."""
        start = time.monotonic()

        try:
            page = await self._get_or_create_page(url)
            old_response = await self._extract_latest_response(page)

            # Type and send
            # Works with both <textarea> and contenteditable DIV (ProseMirror)
            input_el = page.get_by_role("textbox").first
            await input_el.wait_for(state="visible", timeout=10000)
            await input_el.click()
            await asyncio.sleep(0.2)
            # Select all and replace (handles contenteditable)
            await page.keyboard.press("Control+a")
            await page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.3)
            await page.keyboard.press("Enter")

            # Wait for new response
            content = await self._wait_for_response(page, timeout_ms, old_response)
            latency_ms = (time.monotonic() - start) * 1000

            return TransportResponse(
                content=content,
                success=len(content) > 0,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return TransportResponse(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def health(self, url: str) -> bool:
        """Check if a platform is accessible."""
        try:
            page = await self._get_or_create_page(url)
            await page.get_by_role("textbox").first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Disconnect from Chrome."""
        self._pages.clear()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("cdp_disconnected")

    # === Private ===

    async def _get_or_create_page(self, url: str) -> Page:
        """Get existing page for URL or create new one."""
        if url in self._pages and not self._pages[url].is_closed():
            return self._pages[url]

        # Find existing tab
        for context in self._browser.contexts:
            for page in context.pages:
                if url in page.url:
                    self._pages[url] = page
                    return page

        # Create new tab
        context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        self._pages[url] = page
        return page

    async def _wait_for_response(self, page: Page, timeout_ms: int, old_response: str) -> str:
        start = time.monotonic()
        last_text = old_response
        stable_count = 0
        stable_threshold = 4
        new_response_detected = False

        await asyncio.sleep(1.0)

        while (time.monotonic() - start) * 1000 < timeout_ms:
            current_text = await self._extract_latest_response(page)

            if not new_response_detected:
                if current_text and current_text != old_response:
                    new_response_detected = True
                    last_text = current_text
                    stable_count = 0
                else:
                    await asyncio.sleep(0.5)
                    continue

            if current_text and current_text != last_text:
                last_text = current_text
                stable_count = 0
            elif current_text:
                stable_count += 1

            if stable_count >= stable_threshold:
                break

            try:
                stop_btn = page.locator("[data-testid='stop-button']")
                if await stop_btn.count() == 0 and stable_count >= 2:
                    break
            except Exception:
                pass

            await asyncio.sleep(0.5)

        return last_text

    async def _extract_latest_response(self, page: Page) -> str:
        selectors = [
            # ChatGPT
            "[data-message-author-role='assistant']:last-of-type",
            ".markdown.prose:last-of-type",
            # Grok
            "[data-testid*='assistant']:last-of-type",
            ".message-bubble:last-of-type",
            # Generic
            ".markdown:last-of-type",
        ]
        for selector in selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    text = await elements.nth(count - 1).text_content()
                    if text and len(text.strip()) > 0:
                        return text.strip()
            except Exception:
                continue
        return ""
