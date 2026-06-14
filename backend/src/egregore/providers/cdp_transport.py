"""CdpTransport — connects to user's Chrome via CDP.

Uses BrowserManager for page reuse (no new tabs).
Uses NetworkObserver for metadata extraction.

Architecture:
    CdpTransport → BrowserManager → Chrome → Platform
"""

from __future__ import annotations

import asyncio
import time

import structlog
from playwright.async_api import Page

from egregore.providers.browser_manager import BrowserManager
from egregore.providers.network_observer import NetworkObserver
from egregore.providers.transport import TransportResponse, TransportType

logger = structlog.get_logger()


class CdpTransport:
    """Transport via Chrome DevTools Protocol. Reuses pages."""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222") -> None:
        self._browser_manager = BrowserManager(cdp_url)
        self._observers: dict[str, NetworkObserver] = {}

    @property
    def transport_type(self) -> TransportType:
        return TransportType.CDP

    async def connect(self, **kwargs) -> None:
        """Connect to Chrome via CDP."""
        await self._browser_manager.connect()

    async def send(self, url: str, prompt: str, timeout_ms: int = 60000) -> TransportResponse:
        """Send prompt to a platform and wait for response."""
        start = time.monotonic()

        try:
            # Get or create page (reuses existing tab)
            page = await self._browser_manager.get_page(url)

            # Start network observer
            observer = NetworkObserver(page)
            await observer.start()

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

            # Wait for new response
            content = await self._wait_for_response(page, timeout_ms, old_response, old_content_len)
            latency_ms = (time.monotonic() - start) * 1000

            # Get metadata from network
            meta = observer.get_meta()
            await observer.stop()

            return TransportResponse(
                content=content,
                success=len(content) > 0,
                latency_ms=latency_ms,
                metadata={
                    "conversation_id": meta.conversation_id,
                    "model": meta.model,
                    "token_usage": meta.token_usage,
                },
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
            page = await self._browser_manager.get_page(url)
            await page.get_by_role("textbox").first.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Disconnect from Chrome."""
        await self._browser_manager.close()

    # === Private ===

    async def _wait_for_response(self, page: Page, timeout_ms: int, old_response: str, old_content_len: int = 0) -> str:
        start = time.monotonic()
        last_text = old_response
        stable_count = 0
        stable_threshold = 4
        new_response_detected = False

        await asyncio.sleep(1.0)

        while (time.monotonic() - start) * 1000 < timeout_ms:
            current_text = await self._extract_latest_response(page)

            # Virtual list: content grew
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
        selectors = [
            "[data-message-author-role='assistant']:last-of-type",
            ".markdown.prose:last-of-type",
            "[data-testid*='assistant']:last-of-type",
            ".message-bubble:last-of-type",
            ".markdown:last-of-type",
            "[class*='markdown']:last-of-type",
            "[class*='answer']:last-of-type",
            "[aria-label='doc_editor']",
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
