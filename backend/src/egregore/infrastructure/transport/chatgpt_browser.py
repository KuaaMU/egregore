"""ChatGPT Browser Adapter — simple, reliable, Playwright-native.

Design principles:
- Use Playwright built-in capabilities (persistent context, locators, retry)
- No custom recovery state machine
- No browser pool
- No distributed runtime
- Keep it simple enough to actually work

Goal: 24h reliability, 95% success rate.

Lifecycle:
1. launch() — open persistent context, navigate to ChatGPT
2. send(prompt) — type prompt, wait for response, return text
3. health_check() — verify page is functional
4. close() — cleanup

Playwright features used:
- launch_persistent_context() — preserves login state
- Locator API — resilient element finding
- get_by_role() / get_by_test_id() — stable selectors
- wait_for() — wait for elements
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import structlog
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

logger = structlog.get_logger()

CHATGPT_URL = "https://chatgpt.com/"
DEFAULT_DATA_DIR = Path.home() / ".egregore" / "browser_data"


class ChatGPTAdapter:
    """Simple ChatGPT browser adapter.

    Uses Playwright's persistent context to maintain login state.
    No fancy recovery — if it breaks, restart the context.
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        headless: bool = True,
    ) -> None:
        self._data_dir = data_dir or DEFAULT_DATA_DIR / "chatgpt"
        self._headless = headless
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def launch(self) -> None:
        """Launch browser and navigate to ChatGPT.

        Uses persistent context — cookies and login state survive restarts.
        """
        if self._playwright is not None:
            return

        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._data_dir),
            headless=self._headless,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        self._page = await self._context.new_page()
        await self._page.goto(CHATGPT_URL, wait_until="domcontentloaded")

        # Wait for the page to be interactive
        try:
            await self._page.get_by_role("textbox").first.wait_for(timeout=15000)
            logger.info("chatgpt_launched", url=CHATGPT_URL)
        except Exception as e:
            logger.warning("chatgpt_launch_timeout", error=str(e))

    async def send(self, prompt: str, timeout_ms: int = 60000) -> str:
        """Send a prompt and wait for the complete response.

        Simple flow:
        1. Find input
        2. Type prompt
        3. Press Enter (or click send)
        4. Wait for response to appear
        5. Extract response text

        Returns the response text, or empty string on failure.
        """
        if self._page is None:
            raise RuntimeError("Not launched. Call launch() first.")

        page = self._page

        # Step 1: Find and fill input
        input_el = page.get_by_role("textbox").first
        await input_el.wait_for(state="visible", timeout=10000)
        await input_el.click()
        await input_el.fill(prompt)
        await asyncio.sleep(0.3)

        # Step 2: Send (Enter key is more reliable than clicking send button)
        await input_el.press("Enter")

        # Step 3: Wait for response
        # Strategy: wait for the response container to appear and stabilize
        response_text = await self._wait_for_response(page, timeout_ms)

        logger.info("chatgpt_response_received", length=len(response_text))
        return response_text

    async def health_check(self) -> bool:
        """Check if ChatGPT is accessible and interactive."""
        if self._page is None or self._page.is_closed():
            return False

        try:
            # Check if we can find the input
            input_el = self._page.get_by_role("textbox").first
            await input_el.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Shut down the browser."""
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        if self._playwright:
            await self._playwright.stop()
        self._playwright = None
        self._context = None
        self._page = None
        logger.info("chatgpt_closed")

    @property
    def is_ready(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    async def _wait_for_response(self, page: Page, timeout_ms: int) -> str:
        """Wait for ChatGPT's response to complete and extract text.

        Strategy:
        1. Wait for response container to appear
        2. Poll until streaming stops (no text changes for 2 seconds)
        3. Extract final text
        """
        start = time.monotonic()
        last_text = ""
        stable_count = 0
        stable_threshold = 4  # 4 polls with no change = done (4 * 500ms = 2s)

        # Wait a moment for response to start
        await asyncio.sleep(1.0)

        while (time.monotonic() - start) * 1000 < timeout_ms:
            # Get current response text
            current_text = await self._extract_latest_response(page)

            if current_text and current_text != last_text:
                last_text = current_text
                stable_count = 0
            elif current_text:
                stable_count += 1

            # Check if streaming is done
            if stable_count >= stable_threshold:
                break

            # Check for stop button (indicates streaming)
            try:
                stop_btn = page.locator("[data-testid='stop-button']")
                if await stop_btn.count() == 0 and stable_count >= 2:
                    # No stop button and text is stable — done
                    break
            except Exception:
                pass

            await asyncio.sleep(0.5)

        return last_text

    async def _extract_latest_response(self, page: Page) -> str:
        """Extract the latest assistant response from the page.

        Tries multiple selectors (fallback chain).
        """
        selectors = [
            "[data-message-author-role='assistant']:last-of-type",
            ".markdown.prose:last-of-type",
            "[data-testid='assistant-message']:last-of-type",
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
