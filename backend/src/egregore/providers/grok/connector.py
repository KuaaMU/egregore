"""Grok Provider — connects to Grok via Chrome CDP.

Grok URL: https://grok.com/

Grok's web UI is similar to ChatGPT:
- Text input at bottom
- Send button or Enter to send
- Streaming response in main area
- Markdown rendering

Status: Implementation — needs testing against live Grok.
"""

from __future__ import annotations

import asyncio
import time

import structlog
from playwright.async_api import Page, Playwright, async_playwright

from egregore.providers.base import (
    ProviderCapabilities,
    ProviderResponse,
    ProviderStatus,
)

logger = structlog.get_logger()

GROK_URL = "https://grok.com/"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class GrokProvider:
    """Grok provider via Chrome CDP."""

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._page: Page | None = None
        self._status = ProviderStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return "grok"

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            models=["grok-3", "grok-3-mini"],
            vision=True,
            web_search=True,
            thinking=True,
        )

    async def connect(self) -> None:
        """Connect to Chrome via CDP and find Grok tab."""
        if self._playwright is not None:
            return

        self._status = ProviderStatus.CONNECTING
        self._playwright = await async_playwright().start()

        try:
            browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
        except Exception as e:
            self._status = ProviderStatus.BROKEN
            raise RuntimeError(
                f"Cannot connect to Chrome at {self._cdp_url}. "
                f"Start Chrome with: --remote-debugging-port=9222"
            ) from e

        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Find existing Grok tab or create new one
        for page in context.pages:
            if GROK_URL in page.url:
                self._page = page
                logger.info("grok_tab_found", url=page.url)
                break

        if self._page is None:
            self._page = await context.new_page()
            await self._page.goto(GROK_URL, wait_until="domcontentloaded")
            logger.info("grok_tab_created")

        try:
            await self._page.get_by_role("textbox").first.wait_for(timeout=10000)
            self._status = ProviderStatus.IDLE
            logger.info("grok_ready")
        except Exception as e:
            self._status = ProviderStatus.BROKEN
            logger.warning("grok_not_ready", error=str(e))

    async def send(self, prompt: str, timeout_ms: int = 60000) -> ProviderResponse:
        """Send prompt to Grok and wait for response."""
        if self._page is None:
            return ProviderResponse(success=False, error="Not connected")

        self._status = ProviderStatus.GENERATING
        start = time.monotonic()

        try:
            old_response = await self._extract_latest_response(self._page)

            # Type and send
            input_el = self._page.get_by_role("textbox").first
            await input_el.wait_for(state="visible", timeout=10000)
            await input_el.click()
            await input_el.fill(prompt)
            await asyncio.sleep(0.3)
            await input_el.press("Enter")

            # Wait for new response
            content = await self._wait_for_response(self._page, timeout_ms, old_response)
            latency_ms = (time.monotonic() - start) * 1000

            self._status = ProviderStatus.IDLE
            return ProviderResponse(
                content=content,
                model="grok-3",
                latency_ms=latency_ms,
                token_count=len(content.split()),
                success=len(content) > 0,
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            self._status = ProviderStatus.BROKEN
            return ProviderResponse(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def health(self) -> bool:
        if self._page is None or self._page.is_closed():
            return False
        try:
            await self._page.get_by_role("textbox").first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        self._page = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._status = ProviderStatus.DISCONNECTED
        logger.info("grok_disconnected")

    # === Private ===

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

            await asyncio.sleep(0.5)

        return last_text

    async def _extract_latest_response(self, page: Page) -> str:
        """Extract latest response from Grok's DOM.

        Grok uses different selectors than ChatGPT.
        These may need adjustment based on the actual Grok UI.
        """
        selectors = [
            # Grok-specific selectors (may need adjustment)
            "[data-message-author-role='assistant']:last-of-type",
            ".message-bubble:last-of-type",
            ".response-content:last-of-type",
            # Generic fallbacks
            ".markdown:last-of-type",
            "article:last-of-type",
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
