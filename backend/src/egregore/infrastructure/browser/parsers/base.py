"""Base Parser — the port for response parsing.

Parsers are capability-based, not platform-based.

Instead of:
    ChatGPTParser
    ClaudeParser
    GeminiParser

We have:
    MarkdownParser      — extracts markdown from DOM
    ThinkingParser      — extracts thinking/reasoning blocks
    ArtifactParser      — extracts code/files/artifacts
    CodeBlockParser     — extracts and formats code blocks

Why? Because:
- UIs change, capabilities don't
- All platforms produce markdown — the parsing logic is shared
- Thinking blocks differ in CSS but the concept is universal
- New parsers compose with existing ones

Pattern: Strategy / Pipeline

Parsers chain: DOM → MarkdownParser → ThinkingParser → ArtifactParser
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedContent:
    """Result of parsing a provider's response.

    Separates thinking from answer, and artifacts from text.
    This drives the UI: thinking panel, answer panel, artifacts panel.
    """

    answer: str = ""  # The main response text
    thinking: str = ""  # Reasoning/thinking text (if any)
    artifacts: list[str] = None  # Code blocks, files, etc.
    is_streaming: bool = False  # Is the response still being generated?
    raw_html: str = ""  # Raw HTML for debugging

    def __post_init__(self):
        if self.artifacts is None:
            object.__setattr__(self, 'artifacts', [])


class BaseParser(ABC):
    """Base class for response parsers.

    Parsers extract structured content from a web page's DOM.
    Each parser handles one aspect (markdown, thinking, artifacts).
    """

    @abstractmethod
    async def parse(self, page) -> ParsedContent:
        """Parse the current response from the page.

        Args:
            page: A Playwright Page object

        Returns:
            ParsedContent with answer, thinking, artifacts separated
        """
        ...

    @abstractmethod
    async def is_streaming(self, page) -> bool:
        """Check if the response is still being streamed.

        Args:
            page: A Playwright Page object

        Returns:
            True if tokens are still being generated
        """
        ...
