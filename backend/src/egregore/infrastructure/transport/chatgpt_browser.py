"""ChatGPT Browser Connector — connects to user's existing Chrome.

Key insight from Reality Phase #001:
- Cloudflare blocks headless Chromium
- Don't fight Cloudflare
- Attach to the user's existing Chrome instead

Architecture change:
    Before: Egregore → Launch Chromium → ChatGPT (CAPTCHA blocked)
    After:  Egregore → CDP → User's Chrome → ChatGPT (trusted session)

Why this works:
- User's Chrome has cookies, login state, Plus subscription
- User's Chrome has Cloudflare trust (real browsing history)
- No CAPTCHA, no login, no popup
- Completely silent

Usage:
    1. Start Chrome with: chrome.exe --remote-debugging-port=9222
    2. Run Egregore: adapter = ChatGPTConnector(); await adapter.connect()
    3. Send prompts: response = await adapter.send("What is 2+2?")

Playwright feature used: chromium.connect_over_cdp()
"""

from __future__ import annotations

import asyncio
import time

import structlog
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger()

CHATGPT_URL = "https://chatgpt.com/"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class ChatGPTConnector:
    """Connects to user's existing Chrome via CDP.

    Does NOT launch a new browser. Attaches to the user's
    running Chrome instance. This means:
    - No CAPTCHA
    - No login
    - No popup
    - Silent operation
    """

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def connect(self) -> None:
        """Connect to user's running Chrome instance.

        Prerequisites:
        - Chrome must be running with --remote-debugging-port=9222
        - User must be logged into ChatGPT in that Chrome

        This does NOT launch a new browser. It attaches to the existing one.
        """
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()

        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
            logger.info("chrome_connected", cdp_url=self._cdp_url)
        except Exception as e:
            logger.error("chrome_connect_failed", error=str(e))
            raise RuntimeError(
                f"Cannot connect to Chrome at {self._cdp_url}. "
                f"Make sure Chrome is running with --remote-debugging-port=9222"
            ) from e

        # Get existing context or create new one
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
        else:
            self._context = await self._browser.new_context()

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

        # Wait for page to be ready
        try:
            await self._page.get_by_role("textbox").first.wait_for(timeout=10000)
            logger.info("chatgpt_ready")
        except Exception as e:
            logger.warning("chatgpt_not_ready", error=str(e))

    async def send(self, prompt: str, timeout_ms: int = 60000) -> str:
        """Send a prompt and wait for the complete response.

        Flow:
        1. Find input (role=textbox)
        2. Fill prompt
        3. Press Enter
        4. Wait for response to stabilize
        5. Extract text
        """
        if self._page is None:
            raise RuntimeError("Not connected. Call connect() first.")

        page = self._page

        # Record current response BEFORE sending (to detect new response)
        old_response = await self._extract_latest_response(page)

        # Find and fill input
        input_el = page.get_by_role("textbox").first
        await input_el.wait_for(state="visible", timeout=10000)
        await input_el.click()
        await input_el.fill(prompt)
        await asyncio.sleep(0.3)

        # Send
        await input_el.press("Enter")

        # Wait for NEW response (different from old one)
        response_text = await self._wait_for_response(page, timeout_ms, old_response)

        logger.info("response_received", length=len(response_text))
        return response_text

    async def health_check(self) -> bool:
        """Check if ChatGPT is accessible."""
        if self._page is None or self._page.is_closed():
            return False
        try:
            input_el = self._page.get_by_role("textbox").first
            await input_el.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Disconnect (does NOT close the user's browser)."""
        # We don't close the browser — it belongs to the user
        self._page = None
        self._context = None
        self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("disconnected")

    @property
    def is_ready(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    async def _wait_for_response(self, page: Page, timeout_ms: int, old_response: str = "") -> str:
        """Wait for a NEW response (different from old_response) to stabilize.

        Strategy:
        1. Wait for response text to CHANGE from old_response
        2. Then wait for it to STABILIZE (no more changes)
        3. Return the stable text
        """
        start = time.monotonic()
        last_text = old_response
        stable_count = 0
        stable_threshold = 4  # 4 polls with no change = done (2s)
        new_response_detected = False

        await asyncio.sleep(1.0)

        while (time.monotonic() - start) * 1000 < timeout_ms:
            current_text = await self._extract_latest_response(page)

            # Phase 1: Wait for response to CHANGE from old
            if not new_response_detected:
                if current_text and current_text != old_response:
                    new_response_detected = True
                    last_text = current_text
                    stable_count = 0
                else:
                    # Still waiting for new response to appear
                    await asyncio.sleep(0.5)
                    continue

            # Phase 2: Wait for response to STABILIZE
            if current_text and current_text != last_text:
                last_text = current_text
                stable_count = 0
            elif current_text:
                stable_count += 1

            if stable_count >= stable_threshold:
                break

            # Check stop button
            try:
                stop_btn = page.locator("[data-testid='stop-button']")
                if await stop_btn.count() == 0 and stable_count >= 2:
                    break
            except Exception:
                pass

            await asyncio.sleep(0.5)

        return last_text

    async def _extract_latest_response(self, page: Page) -> str:
        """Extract latest assistant response. Tries multiple selectors."""
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
