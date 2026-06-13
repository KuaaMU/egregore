"""Markdown Parser — extracts markdown content from the DOM.

This is the universal parser. Every AI platform renders responses
as markdown in the DOM. The challenge is extracting clean text
from the rendered HTML.

Pattern: Extractor / Transformer

The parser:
1. Finds the response container in the DOM
2. Extracts the innerHTML
3. Cleans up UI artifacts (buttons, tooltips, copy icons)
4. Converts to clean text/markdown
"""

from __future__ import annotations

import re

import structlog
from playwright.async_api import Page

from egregore.infrastructure.browser.parsers.base import BaseParser, ParsedContent

logger = structlog.get_logger()


class MarkdownParser(BaseParser):
    """Extracts markdown text from a provider's response DOM.

    Handles common UI artifacts across platforms:
    - Copy buttons inside code blocks
    - Action buttons (edit, retry, etc.)
    - Streaming cursor animations
    - Nested div structures
    """

    def __init__(self, response_selector: str) -> None:
        """
        Args:
            response_selector: CSS selector for the response container
        """
        self._selector = response_selector

    async def parse(self, page: Page) -> ParsedContent:
        """Extract the latest response text from the page."""
        try:
            # Get the last response element
            elements = page.locator(self._selector)
            count = await elements.count()

            if count == 0:
                return ParsedContent()

            last_element = elements.nth(count - 1)

            # Get text content (strips HTML tags)
            text = await last_element.text_content() or ""

            # Clean up common artifacts
            text = self._clean_text(text)

            return ParsedContent(
                answer=text,
                is_streaming=await self.is_streaming(page),
            )

        except Exception as e:
            logger.warning("markdown_parse_error", error=str(e))
            return ParsedContent()

    async def is_streaming(self, page: Page) -> bool:
        """Check if streaming is still in progress.

        Common patterns across platforms:
        - A "stop" button is visible
        - A streaming CSS class is present
        - The response container has a data-is-streaming attribute
        """
        try:
            # Check for streaming indicators
            stop_btn = page.locator("[data-testid='stop-button']")
            if await stop_btn.count() > 0:
                return True

            streaming = page.locator("[data-is-streaming]")
            if await streaming.count() > 0:
                return True

            # Check for result-streaming class
            result_streaming = page.locator(".result-streaming")
            if await result_streaming.count() > 0:
                return True

            return False

        except Exception:
            return False

    def _clean_text(self, text: str) -> str:
        """Clean up UI artifacts from extracted text.

        Common issues:
        - "Copy code" button text leaks into response
        - "Retry" / "Edit" button text
        - Extra whitespace from DOM structure
        """
        # Remove "Copy code" artifacts
        text = re.sub(r'Copy code\s*', '', text)

        # Remove common button texts
        for artifact in ['Retry', 'Edit', 'Share', 'Good response', 'Bad response']:
            text = text.replace(artifact, '')

        # Normalize whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text
