"""Browser Transport — sends prompts to AI platforms via browser.

Uses BrowserManager (persistent context) for silent operation.
"""

from __future__ import annotations

import asyncio
import time

import structlog
from playwright.async_api import Page

from egregore.providers.browser_manager import BrowserManager
from egregore.providers.transport import TransportResponse, TransportType

logger = structlog.get_logger()


class BrowserTransport:
    """Transport via persistent browser context."""

    def __init__(self, browser_manager: BrowserManager) -> None:
        self._browser_manager = browser_manager

    @property
    def transport_type(self) -> TransportType:
        return TransportType.CDP

    async def connect(self, **kwargs) -> None:
        await self._browser_manager.connect()

    async def send(self, url: str, prompt: str, timeout_ms: int = 60000) -> TransportResponse:
        """Send prompt to a platform and wait for response."""
        start = time.monotonic()

        try:
            page = await self._browser_manager.get_page(url)
            old_response = await self._extract_latest_response(page)
            old_content_len = await self._get_content_length(page)

            # Type and send
            input_el = page.get_by_role("textbox").first
            await input_el.wait_for(state="visible", timeout=10000)
            await input_el.click()
            await asyncio.sleep(0.2)
            await page.keyboard.press("Control+a")
            await page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.3)
            await page.keyboard.press("Enter")

            # Wait for response
            content = await self._wait_for_response(page, timeout_ms, old_response, old_content_len)
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
        try:
            page = await self._browser_manager.get_page(url)
            await page.get_by_role("textbox").first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._browser_manager.close()

    async def _wait_for_response(self, page: Page, timeout_ms: int, old_response: str, old_content_len: int = 0) -> str:
        start = time.monotonic()
        last_text = old_response
        stable_count = 0
        stable_threshold = 4
        new_response_detected = False

        await asyncio.sleep(1.0)

        while (time.monotonic() - start) * 1000 < timeout_ms:
            current_text = await self._extract_latest_response(page)

            if not new_response_detected and current_text == old_response and old_content_len > 0:
                new_len = await self._get_content_length(page)
                if new_len > old_content_len + 10:
                    full_text = await self._get_full_content(page)
                    if full_text and len(full_text) > old_content_len:
                        new_response_detected = True
                        last_text = full_text[old_content_len:]
                        stable_count = 0
                        await asyncio.sleep(0.5)
                        continue

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
        """Extract the latest assistant response from the page.

        Uses platform-specific selectors, ordered by specificity.
        Avoids overly broad selectors that capture page metadata.
        """
        selectors = [
            # ChatGPT — most specific
            "[data-message-author-role='assistant']:last-of-type",
            ".markdown.prose:last-of-type",
            # Grok
            "[data-testid*='assistant']:last-of-type",
            ".message-bubble:last-of-type",
            # Kimi
            ".markdown:last-of-type",
            # Qwen — use specific class, not broad [class*='markdown']
            ".qk-markdown:last-of-type",
            "[class*='answer-common-card']:last-of-type",
            # Doubao — use message container
            "[class*='message-list'] > div:last-child",
        ]
        for selector in selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    text = await elements.nth(count - 1).text_content()
                    if text and len(text.strip()) > 10:
                        # Filter out garbage (JSON, video data, etc.)
                        cleaned = self._clean_response(text.strip())
                        if cleaned:
                            return cleaned
            except Exception:
                continue
        return ""

    def _clean_response(self, text: str) -> str:
        """Filter out garbage from extracted text.

        Some platforms embed JSON metadata, video recommendations, etc.
        We only want the actual response text.
        """
        # Skip if it looks like JSON
        if text.startswith('{') or text.startswith('['):
            return ""
        # Skip if it contains too much structured data
        if '{"data":' in text or '"initialData"' in text:
            # Try to extract just the text before the JSON
            idx = text.find('{"data":')
            if idx > 50:
                return text[:idx].strip()
            return ""
        # Skip very short garbage
        if len(text.strip()) < 5:
            return ""
        return text

    async def _get_content_length(self, page: Page) -> int:
        try:
            el = page.locator("[aria-label='doc_editor']")
            if await el.count() > 0:
                text = await el.first.text_content()
                return len(text)
        except Exception:
            pass
        return 0

    async def _get_full_content(self, page: Page) -> str:
        try:
            el = page.locator("[aria-label='doc_editor']")
            if await el.count() > 0:
                return await el.first.text_content() or ""
        except Exception:
            pass
        return ""
