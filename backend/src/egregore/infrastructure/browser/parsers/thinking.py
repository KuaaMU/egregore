"""Thinking Parser — extracts thinking/reasoning blocks from the DOM.

Some providers (Claude, DeepSeek, Gemini) show their reasoning process.
This parser extracts that separately from the main answer.

The UI typically shows thinking in a collapsible section:
- Claude: "Thinking..." expandable block
- DeepSeek: "Deep Think" section
- Gemini: "Show thinking" toggle

Pattern: Extractor
"""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from egregore.infrastructure.browser.parsers.base import BaseParser, ParsedContent

logger = structlog.get_logger()


class ThinkingParser(BaseParser):
    """Extracts thinking/reasoning text from provider responses.

    Thinking blocks are typically:
    1. In a collapsible/expandable section
    2. Rendered before the main answer
    3. May have a different visual style (dimmer, smaller text)
    """

    def __init__(
        self,
        thinking_selector: str,
        answer_selector: str,
        streaming_selector: str = "",
    ) -> None:
        """
        Args:
            thinking_selector: CSS selector for the thinking block
            answer_selector: CSS selector for the answer block
            streaming_selector: CSS selector for streaming indicator
        """
        self._thinking_selector = thinking_selector
        self._answer_selector = answer_selector
        self._streaming_selector = streaming_selector

    async def parse(self, page: Page) -> ParsedContent:
        """Extract thinking and answer text separately."""
        thinking_text = ""
        answer_text = ""

        try:
            # Extract thinking block
            thinking_elements = page.locator(self._thinking_selector)
            if await thinking_elements.count() > 0:
                thinking_text = await thinking_elements.first.text_content() or ""
                thinking_text = thinking_text.strip()

            # Extract answer block
            answer_elements = page.locator(self._answer_selector)
            count = await answer_elements.count()
            if count > 0:
                answer_text = await answer_elements.nth(count - 1).text_content() or ""
                answer_text = answer_text.strip()

        except Exception as e:
            logger.warning("thinking_parse_error", error=str(e))

        return ParsedContent(
            answer=answer_text,
            thinking=thinking_text,
            is_streaming=await self.is_streaming(page),
        )

    async def is_streaming(self, page: Page) -> bool:
        """Check if thinking/answer is still being generated."""
        if not self._streaming_selector:
            return False
        try:
            streaming = page.locator(self._streaming_selector)
            return await streaming.count() > 0
        except Exception:
            return False
