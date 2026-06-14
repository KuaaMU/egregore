"""Kimi Provider — connects to Kimi via Chrome CDP.

Kimi URL: https://kimi.moonshot.cn/
Status: Stub — implementation after ChatGPT is proven stable.
"""

from __future__ import annotations

from egregore.providers.base import ProviderCapabilities, ProviderStatus


class KimiProvider:
    """Kimi provider via Chrome CDP. (Stub)"""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222") -> None:
        self._cdp_url = cdp_url
        self._status = ProviderStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return "kimi"

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            models=["kimi-k2", "kimi-thinking"],
            vision=True,
            file_upload=True,
            deep_research=True,
            thinking=True,
            web_search=True,
        )
