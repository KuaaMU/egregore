"""ChatGPT Browser Transport — concrete implementation for ChatGPT's web UI.

This is the first real proof of the Browser Runtime pattern.
It demonstrates how the transport/locator/session layers compose.

Pattern: Template Method — base class defines the flow, this class
provides the platform-specific steps.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import structlog
from playwright.async_api import Page

from egregore.domain.executor.locator import LocatorChain
from egregore.infrastructure.browser.locators import chatgpt as locators
from egregore.infrastructure.browser.locators.resolver import LocatorResolver
from egregore.infrastructure.browser.sessions.manager import SessionManager
from egregore.infrastructure.transport.browser import BrowserTransport

logger = structlog.get_logger()

# ChatGPT URLs
CHATGPT_URL = "https://chatgpt.com/"


class ChatGPTBrowserTransport(BrowserTransport):
    """Browser transport for ChatGPT.

    Interacts with ChatGPT's web UI through Playwright.
    """

    def __init__(self, session_manager: SessionManager) -> None:
        super().__init__(
            session_manager=session_manager,
            provider_id="chatgpt",
            base_url=CHATGPT_URL,
        )

    async def _on_page_ready(self, page: Page) -> None:
        """Wait for ChatGPT's chat interface to load."""
        try:
            # Wait for the chat input to appear
            resolver = LocatorResolver(page)
            await resolver.resolve(locators.CHAT_INPUT, timeout_ms=15000)
            logger.info("chatgpt_page_ready")
        except Exception as e:
            logger.warning("chatgpt_page_ready_timeout", error=str(e))

    async def _type_prompt(self, resolver: LocatorResolver, prompt: str) -> None:
        """Type the prompt into ChatGPT's input field.

        ChatGPT uses a contenteditable div, not a standard input.
        We use type_text() which simulates keystrokes.
        """
        # Focus the input
        input_locator = await resolver.resolve(locators.CHAT_INPUT, timeout_ms=10000)
        if input_locator is None:
            raise RuntimeError("Could not find ChatGPT input field")

        await input_locator.click()
        await asyncio.sleep(0.2)

        # Type the prompt
        await input_locator.fill(prompt)
        await asyncio.sleep(0.3)

        logger.info("chatgpt_prompt_typed", length=len(prompt))

    async def _click_send(self, resolver: LocatorResolver) -> None:
        """Click ChatGPT's send button."""
        clicked = await resolver.click(locators.SEND_BUTTON, timeout_ms=5000)
        if not clicked:
            # Fallback: press Enter
            logger.info("chatgpt_send_button_fallback", method="enter_key")
            page = resolver._page
            await page.keyboard.press("Enter")

    async def _parse_stream(
        self, page: Page, resolver: LocatorResolver
    ) -> AsyncIterator[str]:
        """Parse ChatGPT's streaming response.

        ChatGPT streams by updating the DOM. We monitor the response
        container for text changes.

        Strategy:
        1. Wait for response container to appear
        2. Poll for text changes
        3. Yield new tokens as they appear
        4. Stop when streaming indicator disappears
        """
        last_text = ""
        no_change_count = 0
        max_no_change = 10  # Stop after 10 polls with no change

        # Wait for response to start
        await asyncio.sleep(1.0)

        while no_change_count < max_no_change:
            # Get current response text
            current_text = await self._get_response_text(resolver)

            if current_text and current_text != last_text:
                # Extract new token
                new_text = current_text[len(last_text):]
                if new_text:
                    yield new_text
                    last_text = current_text
                    no_change_count = 0
            else:
                no_change_count += 1

            # Check if streaming is done
            is_streaming = await resolver.is_visible(locators.STREAMING_INDICATOR, timeout_ms=1000)
            if not is_streaming and no_change_count >= 3:
                # No streaming indicator and no text changes — done
                break

            await asyncio.sleep(0.3)

        # Final check — get any remaining text
        final_text = await self._get_response_text(resolver)
        if final_text and final_text != last_text:
            yield final_text[len(last_text):]

    async def _get_response_text(self, resolver: LocatorResolver) -> str:
        """Extract the current response text from the page."""
        text = await resolver.get_text(locators.RESPONSE_CONTAINER, timeout_ms=2000)
        return text or ""
