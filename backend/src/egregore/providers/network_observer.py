"""Network Observer — intercepts network requests to extract metadata.

GPT's insight: don't just read DOM, also listen to network.

By intercepting fetch/XHR/SSE requests, we can extract:
- conversation_id
- model name
- token usage
- stop reason
- reasoning effort
- streaming tokens

This is much more reliable than DOM scraping.

Pattern: Observer / Interceptor
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import structlog
from playwright.async_api import Page, Response

logger = structlog.get_logger()


@dataclass
class ConversationMeta:
    """Metadata extracted from network requests."""

    conversation_id: str = ""
    model: str = ""
    token_usage: int = 0
    stop_reason: str = ""
    reasoning_effort: str = ""
    streaming_tokens: list[str] = field(default_factory=list)


class NetworkObserver:
    """Intercepts network requests to extract AI platform metadata.

    Usage:
        observer = NetworkObserver(page)
        await observer.start()
        # ... send prompt and wait ...
        meta = observer.get_meta()
    """

    def __init__(self, page: Page) -> None:
        self._page = page
        self._meta = ConversationMeta()
        self._responses: list[dict] = []

    async def start(self) -> None:
        """Start listening to network responses."""
        self._page.on("response", self._on_response)
        logger.info("network_observer_started")

    async def stop(self) -> None:
        """Stop listening."""
        try:
            self._page.remove_listener("response", self._on_response)
        except Exception:
            pass

    def get_meta(self) -> ConversationMeta:
        """Get extracted metadata."""
        return self._meta

    async def _on_response(self, response: Response) -> None:
        """Called for every network response."""
        url = response.url
        content_type = response.headers.get("content-type", "")

        # Only process API-like responses
        if not self._is_api_response(url, content_type):
            return

        try:
            body = await response.text()
            data = json.loads(body) if body else {}
            self._extract_metadata(url, data)
        except Exception:
            pass

    def _is_api_response(self, url: str, content_type: str) -> bool:
        """Check if this is an API response worth intercepting."""
        api_patterns = [
            "/api/conversation",
            "/api/chat",
            "/v1/chat",
            "/backend-api",
            "conversation_id",
            "stream",
        ]
        return any(p in url for p in api_patterns) or "text/event-stream" in content_type

    def _extract_metadata(self, url: str, data: dict) -> None:
        """Extract metadata from response data."""
        # conversation_id
        if "conversation_id" in data:
            self._meta.conversation_id = data["conversation_id"]

        # model
        if "model" in data:
            self._meta.model = data["model"]
        elif "model_slug" in data:
            self._meta.model = data["model_slug"]

        # usage
        if "usage" in data:
            usage = data["usage"]
            if "total_tokens" in usage:
                self._meta.token_usage = usage["total_tokens"]

        # stop_reason
        if "stop_reason" in data:
            self._meta.stop_reason = data["stop_reason"]

        # Store raw response for debugging
        self._responses.append({"url": url, "data_keys": list(data.keys())[:10]})
