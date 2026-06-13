"""Locator types — domain model for UI element location.

AI platforms change their UIs frequently. Hardcoded CSS selectors
break constantly. The Locator Repository pattern centralizes all
selectors and provides fallback chains.

Design principles:
1. Never use CSS selectors when ARIA/role selectors work
2. Always provide fallback locators (chain of responsibility)
3. Prefer user-visible attributes (get_by_role, get_by_label)
4. Locators are data, not code — easy to update

Pattern: Repository / Chain of Responsibility
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LocatorStrategy(str, Enum):
    """How to locate an element.

    Priority order (most robust to least):
    1. ROLE — semantic, survives most UI changes
    2. ARIA — accessibility labels, fairly stable
    3. TESTID — data-testid, stable if developers maintain it
    4. TEXT — visible text, breaks on i18n
    5. CSS — last resort, breaks on any styling change
    """

    ROLE = "role"
    ARIA = "aria"
    TESTID = "testid"
    TEXT = "text"
    CSS = "css"


@dataclass(frozen=True)
class LocatorDef:
    """A single locator definition.

    Example:
        SEND_BUTTON = LocatorDef(
            strategy=LocatorStrategy.ROLE,
            value="button",
            name="Send",  # role-specific attribute
        )
    """

    strategy: LocatorStrategy
    value: str
    name: str = ""  # For role: the accessible name
    timeout_ms: int = 5000


@dataclass(frozen=True)
class LocatorChain:
    """A chain of fallback locators for a single element.

    Try each locator in order. Use the first one that finds an element.

    Example:
        SEND_BUTTON = LocatorChain(locators=[
            LocatorDef(ROLE, "button", name="Send"),
            LocatorDef(ARIA, "[aria-label='Send message']"),
            LocatorDef(TESTID, "[data-testid='send-button']"),
            LocatorDef(TEXT, "Send"),
        ])
    """

    name: str  # Human-readable name (e.g., "SEND_BUTTON")
    locators: list[LocatorDef] = field(default_factory=list)

    @property
    def primary(self) -> LocatorDef | None:
        return self.locators[0] if self.locators else None

    @property
    def fallbacks(self) -> list[LocatorDef]:
        return self.locators[1:] if len(self.locators) > 1 else []
