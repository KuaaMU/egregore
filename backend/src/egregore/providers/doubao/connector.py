"""Doubao Provider — connects to Doubao via Chrome CDP.

Doubao URL: https://www.doubao.com/
Status: Stub — implementation after ChatGPT is proven stable.
"""

from __future__ import annotations

from egregore.providers.base import ProviderCapabilities, ProviderStatus


class DoubaoProvider:
    """Doubao provider via Chrome CDP. (Stub)"""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222") -> None:
        self._cdp_url = cdp_url
        self._status = ProviderStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return "doubao"

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            models=["doubao-pro"],
            vision=True,
            file_upload=True,
            web_search=True,
        )
