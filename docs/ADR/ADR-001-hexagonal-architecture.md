# ADR-001: Hexagonal Architecture

## Status

Accepted

## Context

Egregore is a multi-LLM collaboration platform that will evolve from a simple round-table tool into an operating system for intelligence. We need an architecture that:

1. Allows hot-swapping providers without changing core logic
2. Supports testing with mock implementations
3. Enables gradual evolution from monolith to distributed system
4. Keeps business logic free from infrastructure concerns

## Decision

We adopt **Hexagonal Architecture** (Ports & Adapters).

### Structure

- **Domain Layer**: Entities (Message, Conversation) and Ports (BaseProvider)
- **Application Layer**: Orchestrators that compose domain objects
- **Infrastructure Layer**: Adapters that implement ports (OpenAI, Anthropic, Mock)
- **API Layer**: FastAPI routes, thin controllers

### Key Patterns

- **Port**: `BaseProvider` abstract class defines the interface
- **Adapter**: `OpenAIProvider`, `AnthropicProvider` implement the port
- **Composition Root**: `create_app()` wires everything together
- **Registry**: Manages provider lifecycle

## Alternatives Considered

### 1. Simple Monolith
- Pros: Fast to build
- Cons: Tightly coupled, hard to test, hard to evolve
- Verdict: Rejected — doesn't scale to V6 agent society

### 2. Microservices
- Pros: Independent deployment, clear boundaries
- Cons: Premature complexity, operational overhead for a solo/small team
- Verdict: Rejected — too early; can evolve into this later

### 3. Clean Architecture (full)
- Pros: Maximum separation
- Cons: Too many layers for early stage, ceremony without benefit
- Verdict: Rejected — hexagonal is simpler and sufficient

## Consequences

### Positive
- Providers are independently replaceable
- Orchestrator is testable with mock providers
- Clear dependency direction (infra → domain)
- Easy to add new providers

### Negative
- More files than a monolith
- Requires discipline to maintain layer boundaries
- Initial setup is slower

### Mitigations
- Start with minimal layers
- Add complexity only when needed
- Document patterns as we go
