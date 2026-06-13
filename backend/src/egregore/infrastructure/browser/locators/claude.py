"""Claude locators — centralized selectors for Claude's web UI.

All Claude selectors live here. When Anthropic updates their UI,
this is the ONLY file that needs updating.
"""

from egregore.domain.executor.locator import LocatorChain, LocatorDef, LocatorStrategy

# === Page Load ===

CHAT_LOADED = LocatorChain(
    name="CHAT_LOADED",
    locators=[
        LocatorDef(LocatorStrategy.ROLE, "textbox", name="Write your prompt"),
        LocatorDef(LocatorStrategy.CSS, "[contenteditable='true']"),
    ],
)

# === Input ===

CHAT_INPUT = LocatorChain(
    name="CHAT_INPUT",
    locators=[
        LocatorDef(LocatorStrategy.ROLE, "textbox", name="Write your prompt"),
        LocatorDef(LocatorStrategy.ARIA, "[contenteditable='true']"),
        LocatorDef(LocatorStrategy.CSS, ".ProseMirror"),
    ],
)

# === Send Button ===

SEND_BUTTON = LocatorChain(
    name="SEND_BUTTON",
    locators=[
        LocatorDef(LocatorStrategy.ARIA, "[aria-label='Send Message']"),
        LocatorDef(LocatorStrategy.ROLE, "button", name="Send Message"),
    ],
)

# === Response Container ===

RESPONSE_CONTAINER = LocatorChain(
    name="RESPONSE_CONTAINER",
    locators=[
        LocatorDef(LocatorStrategy.CSS, "[data-is-streaming]"),
        LocatorDef(LocatorStrategy.CSS, ".font-claude-message:last-of-type"),
    ],
)

# === Streaming Detection ===

STREAMING_INDICATOR = LocatorChain(
    name="STREAMING_INDICATOR",
    locators=[
        LocatorDef(LocatorStrategy.CSS, "[data-is-streaming]"),
        LocatorDef(LocatorStrategy.CSS, ".result-streaming"),
    ],
)

# === Login Detection ===

LOGIN_PAGE = LocatorChain(
    name="LOGIN_PAGE",
    locators=[
        LocatorDef(LocatorStrategy.TEXT, "Log in"),
        LocatorDef(LocatorStrategy.TEXT, "Sign in"),
    ],
)

# === New Chat ===

NEW_CHAT_BUTTON = LocatorChain(
    name="NEW_CHAT_BUTTON",
    locators=[
        LocatorDef(LocatorStrategy.ARIA, "[aria-label='New chat']"),
        LocatorDef(LocatorStrategy.ROLE, "link", name="New chat"),
    ],
)
