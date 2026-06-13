# Egregore Architecture

## Overview

Egregore is an event-driven intelligence system for multi-LLM collaboration.

```
Egregore = Browser Runtime + Collective Intelligence Engine
```

The Browser Runtime is the transport layer. The Collective Intelligence
Engine (Consensus, Debate, Memory) sits on top.

## Core Architecture: Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────┐
│                  Collective Intelligence                 │
│        (Round Table → Consensus → Debate → Memory)       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                  Application Layer                        │
│     ┌──────────────┐  ┌──────────────┐                   │
│     │  Orchestrator │  │  Event Bus   │                   │
│     └──────┬───────┘  └──────────────┘                   │
└────────────┼────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────┐
│                    Domain Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Provider │  │ Transport│  │ Executor │  │ Health   │ │
│  │ (Port)   │  │ (Port)   │  │ Events   │  │ State    │ │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └──────────┘ │
└───────┼─────────────┼───────────────────────────────────┘
        │             │
┌───────▼─────────────▼───────────────────────────────────┐
│              Infrastructure Layer                         │
│                                                          │
│  ┌─────────────────────────────────────────────────┐     │
│  │           Browser Runtime                        │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │     │
│  │  │ Chromium │ │ Session  │ │ Page     │        │     │
│  │  │ Runtime  │ │ Manager  │ │ Pool     │        │     │
│  │  └──────────┘ └──────────┘ └──────────┘        │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │     │
│  │  │ Locator  │ │ Stream   │ │ Health   │        │     │
│  │  │ Resolver │ │ Parsers  │ │ Monitor  │        │     │
│  │  └──────────┘ └──────────┘ └──────────┘        │     │
│  │  ┌──────────┐ ┌──────────┐                     │     │
│  │  │ Recovery │ │ Locators │                     │     │
│  │  │ Manager  │ │ (per UI) │                     │     │
│  │  └──────────┘ └──────────┘                     │     │
│  └─────────────────────────────────────────────────┘     │
│                                                          │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │ Browser Transport│  │  API Transport  │               │
│  │ (Playwright)     │  │  (httpx/openai) │               │
│  └────────┬────────┘  └────────┬────────┘               │
│           │                    │                         │
│  ┌────────▼────────────────────▼────────┐               │
│  │         Provider Adapter              │               │
│  │  (BrowserTransport → BaseProvider)    │               │
│  └──────────────────────────────────────┘               │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  OpenAI  │  │ Anthropic│  │  Mock    │               │
│  │ (API)    │  │  (API)   │  │ Adapter  │               │
│  └──────────┘  └──────────┘  └──────────┘               │
└──────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### Domain Layer (`domain/`)

Zero infrastructure dependencies. Defines:

- **`domain/transport/base.py`**: `BaseTransport` — port for sending prompts and receiving event streams
- **`domain/providers/base.py`**: `BaseProvider` — port for the orchestrator (complete/stream)
- **`domain/executor/events.py`**: `StreamEvent` — events emitted during response streaming
- **`domain/executor/locator.py`**: `LocatorChain`, `LocatorDef` — centralized selector model
- **`domain/health/types.py`**: `ProviderHealth`, `HealthStatus` — health state machine
- **`domain/session/types.py`**: `SessionState`, `SessionInfo` — session lifecycle
- **`domain/entities/message.py`**: `Message`, `Conversation` — core entities
- **`domain/events/bus.py`**: `EventBus` — async pub/sub

### Application Layer (`application/`)

- **`RoundTableOrchestrator`**: Dispatches to all providers in parallel

### Infrastructure Layer (`infrastructure/`)

#### Browser Runtime (`infrastructure/browser/`)

The transport infrastructure:

- **`runtime/chromium.py`**: `ChromiumRuntime` — Playwright lifecycle, persistent contexts
- **`sessions/manager.py`**: `SessionManager` — long-lived session management
- **`locators/resolver.py`**: `LocatorResolver` — resolves LocatorChains to Playwright locators
- **`locators/chatgpt.py`**: ChatGPT-specific selectors (centralized)
- **`locators/claude.py`**: Claude-specific selectors (centralized)
- **`health/monitor.py`**: `HealthMonitor` — periodic health checks, state machine
- **`recovery/manager.py`**: `RecoveryManager` — escalation-based recovery

#### Transport (`infrastructure/transport/`)

- **`browser.py`**: `BrowserTransport` — abstract browser transport (Template Method)
- **`chatgpt_browser.py`**: `ChatGPTBrowserTransport` — ChatGPT-specific implementation
- **`provider_adapter.py`**: `BrowserProviderAdapter` — bridges BrowserTransport → BaseProvider

#### Providers (`infrastructure/providers/`)

API-based providers (kept for direct API access):

- **`openai_provider.py`**: OpenAI API adapter
- **`anthropic_provider.py`**: Anthropic API adapter
- **`mock.py`**: Mock provider for testing

## Key Design Decisions

### 1. Transport Abstraction

```
Provider → Transport → Runtime → BrowserContext
```

Providers don't know if they're using a browser or API.
Transports can be swapped without changing providers.

### 2. Event Streams

```python
async for event in transport.send(prompt):
    match event.type:
        case StreamEventType.TOKEN: handle_token(event)
        case StreamEventType.DONE: handle_done(event)
```

Everything is an event. The EventBus makes all events observable.

### 3. Locator Repository

Never scatter selectors. All selectors live in `locators/*.py`.
Each locator has fallbacks (role → aria → testid → text → css).

### 4. Health State Machine

```
UNKNOWN → HEALTHY ↔ DEGRADED → RECOVERING → HEALTHY
                              → FAILED → RECOVERING
HEALTHY → EXPIRED → RECOVERING
```

Invalid transitions are rejected.

### 5. Recovery Escalation

```
Page Refresh → Reopen Page → Recreate Context → Restart Browser
```

Each level is tried before escalating.

## Data Flow: Browser Round Table

```
User Prompt
    → RoundTableOrchestrator.execute()
    → For each provider:
        → BrowserProviderAdapter.complete()
        → BrowserTransport.send()
        → SessionManager.get_or_create()
        → LocatorResolver.resolve(CHAT_INPUT)
        → Type prompt, click send
        → _parse_stream() → StreamEvent tokens
        → Collect into Message
    → Return RoundTableResult
```

## Event Flow

```
PROMPT_RECEIVED
    → PROVIDER_DISPATCHED (×N)
    → STREAM_STARTED (×N)
    → STREAM_TOKEN (×N, many times)
    → STREAM_COMPLETED (×N)
    → PROVIDER_COMPLETED (×N)
    → CONSENSUS_STARTED (future)
    → CONSENSUS_COMPLETED (future)
```

## Roadmap

| Version | Feature | Status |
|---------|---------|--------|
| V0.5 | Browser Runtime | 🔄 Current |
| V1 | Multi-LLM Round Table | ✅ Done |
| V1.5 | Consensus Engine | Planned |
| V2 | Debate Engine | Planned |
| V3 | Dynamic Weighting | Planned |
| V4 | Memory System | Planned |
| V5 | Agent Society | Planned |
