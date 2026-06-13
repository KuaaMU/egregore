# ADR-002: Browser Runtime as Transport Layer Foundation

## Status

Accepted (revised)

## Context

Egregore needs to interact with multiple AI platforms. The first version used
direct API calls (OpenAI, Anthropic). This works but has limitations:

1. Not all platforms have public APIs (Grok, some Gemini features)
2. API access may be restricted or expensive
3. Web UIs often have features APIs don't (search, plugins, artifacts)

## Decision

Build a **Browser Runtime** using Playwright as the primary transport layer.

### Key Architectural Refinements

#### 1. Transport Abstraction

```
Provider → Transport → Runtime → BrowserContext
```

Providers don't know if they're using a browser or API. The transport
is the abstraction layer. This allows:
- BrowserTransport for web UI automation
- ApiTransport for direct API calls
- MockTransport for testing

#### 2. Event Streams (not request-response)

```python
async for event in transport.send(prompt):
    match event.type:
        case StreamEventType.TOKEN: handle_token(event)
        case StreamEventType.DONE: handle_done(event)
```

Everything is an async generator of StreamEvents. This enables:
- Real-time UI updates
- Event bus integration
- Composability (consensus/debate can observe streams)
- Cancellation support

#### 3. Health State Machine (not if-else)

```
UNKNOWN → HEALTHY ↔ DEGRADED → RECOVERING → HEALTHY
                              → FAILED → RECOVERING
HEALTHY → EXPIRED → RECOVERING
```

Invalid transitions are rejected. State drives behavior.

#### 4. Recovery Escalation

```
Page Refresh → Reopen Page → Recreate Context → Restart Browser
```

Each level is tried before escalating. Failures are expected;
recovery is a feature.

#### 5. Long-lived Workers

```python
# WRONG: per-request browser launch
browser = await launch()
page = await browser.new_page()
# ... use page ...
await browser.close()

# RIGHT: persistent context, reused across requests
context = await launch_persistent_context(user_data_dir)
session = Session(context=context)
page = await session.ensure_page()
```

Sessions persist across requests. Login state, cookies, and
localStorage survive restarts.

## Architecture

```
infrastructure/
    browser/
        runtime/
            chromium.py          # Playwright lifecycle
        sessions/
            manager.py           # Long-lived session management
        pools/                   # (future) page/browser pools
        locators/
            chatgpt.py           # Centralized selectors
            claude.py
            resolver.py          # LocatorChain → Playwright Locator
        parsers/                 # (future) stream parsers
        health/
            monitor.py           # Health state machine
        recovery/
            manager.py           # Escalation-based recovery
    transport/
        browser.py               # Abstract browser transport
        chatgpt_browser.py       # ChatGPT-specific implementation
        provider_adapter.py      # BrowserTransport → BaseProvider
    providers/
        openai_provider.py       # API-based (kept)
        anthropic_provider.py    # API-based (kept)
```

## Alternatives Considered

### API-first only
- Pros: Reliable, fast
- Cons: Not universal, rate-limited
- Verdict: Keep as secondary transport

### Hybrid (API where available, browser fallback)
- Pros: Best performance when API works
- Cons: Two models to maintain
- Verdict: Future optimization, not V0.5

## Consequences

### Positive
- Universal platform access (any web UI)
- Single interaction model
- Login state persists across restarts
- Event streams enable real-time UI

### Negative
- Higher resource usage (browser contexts ~200-500MB each)
- Selector fragility (UIs change)
- Slower than API calls

### Mitigations
- Locator repository with fallback chains
- Health monitoring detects failures early
- Recovery system handles failures automatically
- Resource pool management (future)
