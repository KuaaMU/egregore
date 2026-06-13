"""Browser Runtime — the transport infrastructure for Egregore.

This package contains the browser automation layer that allows
Egregore to interact with AI platforms through their web UIs.

Architecture:
    Runtime (Playwright) → Session Manager → Browser Transport → Provider
"""

from egregore.infrastructure.browser.runtime.chromium import ChromiumRuntime
from egregore.infrastructure.browser.sessions.manager import Session, SessionManager
from egregore.infrastructure.browser.locators.resolver import LocatorResolver
from egregore.infrastructure.browser.health.monitor import HealthMonitor
from egregore.infrastructure.browser.recovery.manager import RecoveryManager

__all__ = [
    "ChromiumRuntime",
    "Session",
    "SessionManager",
    "LocatorResolver",
    "HealthMonitor",
    "RecoveryManager",
]
