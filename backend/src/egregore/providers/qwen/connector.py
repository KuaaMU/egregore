"""Qwen Provider — connects to Qwen Studio via Chrome CDP.

Qwen URL: https://tongyi.aliyun.com/qianwen/
Status: Stub — implementation after ChatGPT is proven stable.
"""

from __future__ import annotations

from egregore.providers.base import ProviderCapabilities, ProviderStatus


class QwenProvider:
    """Qwen provider via Chrome CDP. (Stub)"""

    def __init__(self, cdp_url: str = "http://127.0.0.1:9222") -> None:
        self._cdp_url = cdp_url
        self._status = ProviderStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return "qwen"

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            models=["qwen3", "qwen3-thinking"],
            vision=True,
            file_upload=True,
            thinking=True,
            web_search=True,
        )
