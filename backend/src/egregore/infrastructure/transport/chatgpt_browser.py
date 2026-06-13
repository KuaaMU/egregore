"""ChatGPT Browser Connector — connects to user's Chrome via CDP.

Architecture:
    Egregore → CDP → User's Chrome → ChatGPT

Why CDP instead of launchPersistentContext?
- Silent (no browser window popup)
- Uses user's existing login, cookies, Plus subscription
- Cloudflare trust (user's real browser)

Why not worry about "lower fidelity"?
- We only need: fill input, press Enter, read text
- We don't need: page.route(), tracing, video, network interception
- CDP works fine for our use case

Usage:
    1. Start Chrome: chrome.exe --remote-debugging-port=9222 --user-data-dir=...
    2. connector = ChatGPTConnector()
    3. await connector.connect()
    4. response = await connector.send("What is 2+2?")
"""

from __future__ import annotations

import asyncio
import time

import structlog
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger()

CHATGPT_URL = "https://chatgpt.com/"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class ChatGPTConnector:
    """Connects to user's Chrome via CDP. Silent, no popup."""

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def connect(self) -> None:
        """Connect to user's Chrome. Browser must be running with --remote-debugging-port."""
        if self._playwright is not None:
            return

        self._playwright = await async_playwright().start()
        try:
            browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect to Chrome at {self._cdp_url}. "
                f"Start Chrome with: --remote-debugging-port=9222 --user-data-dir=..."
            ) from e

        contexts = browser.contexts
        self._context = contexts[0] if contexts else await browser.new_context()

        # Find existing ChatGPT tab or create new one
        for page in self._context.pages:
            if CHATGPT_URL in page.url:
                self._page = page
                logger.info("chatgpt_tab_found", url=page.url)
                break

        if self._page is None:
            self._page = await self._context.new_page()
            await self._page.goto(CHATGPT_URL, wait_until="domcontentloaded")
            logger.info("chatgpt_tab_created")

        try:
            await self._page.get_by_role("textbox").first.wait_for(timeout=10000)
            logger.info("chatgpt_ready")
        except Exception as e:
            logger.warning("chatgpt_not_ready", error=str(e))

    async def send(self, prompt: str, timeout_ms: int = 60000) -> str:
        """Send prompt, wait for response, return text."""
        if self._page is None:
            raise RuntimeError("Not connected. Call connect() first.")

        page = self._page
        old_response = await self._extract_latest_response(page)

        # Type and send
        input_el = page.get_by_role("textbox").first
        await input_el.wait_for(state="visible", timeout=10000)
        await input_el.click()
        await input_el.fill(prompt)
        await asyncio.sleep(0.3)
        await input_el.press("Enter")

        # Wait for NEW response
        response_text = await self._wait_for_response(page, timeout_ms, old_response)
        logger.info("response_received", length=len(response_text))
        return response_text

    async def health_check(self) -> bool:
        """Check if ChatGPT is accessible."""
        if self._page is None or self._page.is_closed():
            return False
        try:
            await self._page.get_by_role("textbox").first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Disconnect (does NOT close user's browser)."""
        self._page = None
        self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("disconnected")

    @property
    def is_ready(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    async def _wait_for_response(self, page: Page, timeout_ms: int, old_response: str) -> str:
        """Wait for response to change from old_response, then stabilize."""
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
        """Extract latest assistant response text."""
        selectors = [
            "[data-message-author-role='assistant']:last-of-type",
            ".markdown.prose:last-of-type",
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
