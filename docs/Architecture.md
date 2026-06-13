# Egregore Architecture

## Overview

Egregore is an event-driven intelligence system for multi-LLM collaboration.

## Core Architecture: Hexagonal (Ports & Adapters)

```
┌─────────────────────────────────────────────────┐
│               Frontend (Next.js)                │
└─────────────────────┬───────────────────────────┘
                      │ HTTP REST / WebSocket
┌─────────────────────▼───────────────────────────┐
│            API Layer (FastAPI)                   │
│         Routes → Schemas → Responses             │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│          Application Layer                       │
│  ┌─────────────────┐  ┌──────────────┐          │
│  │    Orchestrator  │  │   Event Bus  │          │
│  └────────┬────────┘  └──────┬───────┘          │
└───────────┼──────────────────┼──────────────────┘
            │                  │
┌───────────▼──────────────────▼──────────────────┐
│              Domain Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Provider │  │ Message  │  │  Event   │       │
│  │ (Port)   │  │ (Entity) │  │ (Entity) │       │
│  └────┬─────┘  └──────────┘  └──────────┘       │
└───────┼─────────────────────────────────────────┘
        │ implements
┌───────▼─────────────────────────────────────────┐
│        Infrastructure Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  OpenAI  │  │ Anthropic│  │  Mock    │       │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │       │
│  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────┘
```

## Layers

### Domain Layer (`domain/`)

The core of the system. Contains:

- **Entities** (`entities/message.py`): Message, Conversation, ProviderMeta
- **Ports** (`providers/base.py`): BaseProvider abstract class
- **Events** (`events/bus.py`): EventBus, Event, EventType

**Rule**: Domain layer has ZERO dependencies on infrastructure or API layers.

### Application Layer (`application/`)

Orchestrates domain objects to fulfill use cases:

- **RoundTableOrchestrator**: Dispatches prompts to all providers in parallel
- **Services**: (future) Summary, Consensus, Debate

### Infrastructure Layer (`infrastructure/`)

Concrete implementations of domain ports:

- **OpenAIProvider**: OpenAI-compatible API adapter
- **AnthropicProvider**: Claude API adapter
- **MockProvider**: Testing and development

### API Layer (`api/`)

FastAPI routes and schemas:

- **Routes** (`routers/chat.py`): HTTP endpoints
- **Schemas** (`schemas/chat.py`): Request/response DTOs
- **App Factory** (`app.py`): Composition root

## Event-Driven Architecture

Everything is an event. The EventBus enables:

1. **Decoupling**: Providers don't know who listens
2. **Observability**: Every step is logged
3. **Extensibility**: Add handlers without changing producers
4. **Future**: WebSocket push, event sourcing, replay

### Event Flow

```
User Prompt
    → PROMPT_RECEIVED
    → PROVIDER_DISPATCHED (×N)
    → PROVIDER_STREAM_CHUNK (×N, streaming)
    → PROVIDER_COMPLETED (×N)
    → CONSENSUS_STARTED
    → CONSENSUS_COMPLETED
```

## Provider System

### Interface (Port)

```python
class BaseProvider(ABC):
    async def complete(messages) -> Message
    async def stream(messages) -> AsyncIterator[str]
    async def health_check() -> bool
```

### Registry

Providers register at startup. The orchestrator asks the registry for active providers.

### Adding a New Provider

1. Create `infrastructure/providers/my_provider.py`
2. Implement `BaseProvider`
3. Register in `api/app.py` factory

## Frontend Architecture

Three-column layout:

- **Left**: Conversation history sidebar
- **Middle**: Round table view (prompt, consensus, response cards)
- **Right**: Provider detail panel

Components communicate via React state (future: Zustand store).

## Roadmap

| Version | Feature | Status |
|---------|---------|--------|
| V1 | Multi-LLM Round Table | ✅ Current |
| V2 | Consensus Engine | Planned |
| V3 | Debate Engine | Planned |
| V4 | Dynamic Weighting | Planned |
| V5 | Memory System | Planned |
| V6 | Agent Society | Planned |
