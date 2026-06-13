"""ChatGPT locators — centralized selectors for ChatGPT's web UI.

All ChatGPT selectors live here. When OpenAI changes their UI,
this is the ONLY file that needs updating.

Design principles:
1. Prefer role/ARIA selectors over CSS
2. Every locator has fallbacks
3. Comments explain what each selector targets
4. Regularly verify selectors still work

IMPORTANT: These selectors WILL break as OpenAI updates their UI.
The fallback chain ensures graceful degradation.
"""

from egregore.domain.executor.locator import LocatorChain, LocatorDef, LocatorStrategy

# === Page Load ===

CHAT_LOADED = LocatorChain(
    name="CHAT_LOADED",
    locators=[
        # The main chat input area
        LocatorDef(LocatorStrategy.ROLE, "textbox", name="Message ChatGPT"),
        LocatorDef(LocatorStrategy.ARIA, "[contenteditable='true']"),
        LocatorDef(LocatorStrategy.CSS, "#prompt-textarea"),
    ],
)

# === Input ===

CHAT_INPUT = LocatorChain(
    name="CHAT_INPUT",
    locators=[
        LocatorDef(LocatorStrategy.ROLE, "textbox", name="Message ChatGPT"),
        LocatorDef(LocatorStrategy.ARIA, "[id='prompt-textarea']"),
        LocatorDef(LocatorStrategy.CSS, "#prompt-textarea"),
        LocatorDef(LocatorStrategy.CSS, "[contenteditable='true']"),
    ],
)

# === Send Button ===

SEND_BUTTON = LocatorChain(
    name="SEND_BUTTON",
    locators=[
        LocatorDef(LocatorStrategy.ARIA, "[data-testid='send-button']"),
        LocatorDef(LocatorStrategy.ROLE, "button", name="Send prompt"),
        LocatorDef(LocatorStrategy.CSS, "button[aria-label='Send prompt']"),
    ],
)

# === Stop Button (during streaming) ===

STOP_BUTTON = LocatorChain(
    name="STOP_BUTTON",
    locators=[
        LocatorDef(LocatorStrategy.ARIA, "[data-testid='stop-button']"),
        LocatorDef(LocatorStrategy.ROLE, "button", name="Stop generating"),
    ],
)

# === Response Container ===

RESPONSE_CONTAINER = LocatorChain(
    name="RESPONSE_CONTAINER",
    locators=[
        # The latest assistant message
        LocatorDef(LocatorStrategy.CSS, "[data-message-author-role='assistant']:last-of-type"),
        LocatorDef(LocatorStrategy.CSS, ".markdown.prose:last-of-type"),
    ],
)

# === Streaming Detection ===

STREAMING_INDICATOR = LocatorChain(
    name="STREAMING_INDICATOR",
    locators=[
        # The stop button appears during streaming
        LocatorDef(LocatorStrategy.ARIA, "[data-testid='stop-button']"),
        # Streaming cursor/animation
        LocatorDef(LocatorStrategy.CSS, ".result-streaming"),
    ],
)

# === Login Detection ===

LOGIN_PAGE = LocatorChain(
    name="LOGIN_PAGE",
    locators=[
        LocatorDef(LocatorStrategy.TEXT, "Log in"),
        LocatorDef(LocatorStrategy.TEXT, "Sign up"),
        LocatorDef(LocatorStrategy.ROLE, "button", name="Log in"),
    ],
)

# === Error Detection ===

ERROR_BANNER = LocatorChain(
    name="ERROR_BANNER",
    locators=[
        LocatorDef(LocatorStrategy.CSS, "[role='alert']"),
        LocatorDef(LocatorStrategy.TEXT, "Something went wrong"),
        LocatorDef(LocatorStrategy.TEXT, "Network error"),
    ],
)

# === New Chat ===

NEW_CHAT_BUTTON = LocatorChain(
    name="NEW_CHAT_BUTTON",
    locators=[
        LocatorDef(LocatorStrategy.ARIA, "[data-testid='new-chat']"),
        LocatorDef(LocatorStrategy.ROLE, "link", name="New chat"),
    ],
)
