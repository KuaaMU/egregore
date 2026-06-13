"""Locator Resolver — converts LocatorChain to Playwright Locator.

This is the bridge between our domain model (LocatorChain)
and Playwright's locator API.

The resolver tries each locator in the chain until one finds an element.
This provides resilience against UI changes.

Pattern: Chain of Responsibility
"""

from __future__ import annotations

import structlog
from playwright.async_api import Page

from egregore.domain.executor.locator import LocatorChain, LocatorDef, LocatorStrategy

logger = structlog.get_logger()


class LocatorResolver:
    """Resolves LocatorChains to Playwright Locators.

    Usage:
        resolver = LocatorResolver(page)
        element = await resolver.resolve(CHAT_INPUT)
        if element:
            await element.fill("Hello")
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    async def resolve(
        self,
        chain: LocatorChain,
        timeout_ms: int = 5000,
    ):
        """Try each locator in the chain. Return the first match.

        Args:
            chain: The locator chain to resolve
            timeout_ms: Timeout per individual locator attempt

        Returns:
            A Playwright Locator if found, None otherwise
        """
        for i, loc_def in enumerate(chain.locators):
            try:
                locator = self._build_locator(loc_def)
                # Check if element exists (with short timeout)
                await locator.first.wait_for(
                    state="visible",
                    timeout=timeout_ms if i == 0 else 2000,
                )
                if i > 0:
                    logger.info(
                        "locator_fallback_used",
                        chain=chain.name,
                        fallback_index=i,
                        strategy=loc_def.strategy,
                    )
                return locator.first
            except Exception:
                continue

        logger.warning("locator_chain_exhausted", chain=chain.name)
        return None

    async def is_visible(self, chain: LocatorChain, timeout_ms: int = 2000) -> bool:
        """Check if any locator in the chain finds a visible element."""
        locator = await self.resolve(chain, timeout_ms=timeout_ms)
        return locator is not None

    async def click(self, chain: LocatorChain, timeout_ms: int = 5000) -> bool:
        """Click the first matching element."""
        locator = await self.resolve(chain, timeout_ms=timeout_ms)
        if locator:
            await locator.click()
            return True
        return False

    async def fill(self, chain: LocatorChain, text: str, timeout_ms: int = 5000) -> bool:
        """Fill the first matching input element."""
        locator = await self.resolve(chain, timeout_ms=timeout_ms)
        if locator:
            await locator.fill(text)
            return True
        return False

    async def type_text(self, chain: LocatorChain, text: str, timeout_ms: int = 5000) -> bool:
        """Type text character by character (for input fields that don't support fill)."""
        locator = await self.resolve(chain, timeout_ms=timeout_ms)
        if locator:
            await locator.type(text, delay=10)
            return True
        return False

    async def get_text(self, chain: LocatorChain, timeout_ms: int = 5000) -> str | None:
        """Get text content from the first matching element."""
        locator = await self.resolve(chain, timeout_ms=timeout_ms)
        if locator:
            return await locator.text_content()
        return None

    def _build_locator(self, loc_def: LocatorDef):
        """Convert a LocatorDef to a Playwright Locator.

        Maps our domain strategies to Playwright's locator API.
        """
        match loc_def.strategy:
            case LocatorStrategy.ROLE:
                role_kwargs = {"name": loc_def.name} if loc_def.name else {}
                return self._page.get_by_role(loc_def.value, **role_kwargs)
            case LocatorStrategy.ARIA:
                return self._page.locator(loc_def.value)
            case LocatorStrategy.TESTID:
                return self._page.get_by_test_id(loc_def.value)
            case LocatorStrategy.TEXT:
                return self._page.get_by_text(loc_def.value)
            case LocatorStrategy.CSS:
                return self._page.locator(loc_def.value)
            case _:
                return self._page.locator(loc_def.value)
