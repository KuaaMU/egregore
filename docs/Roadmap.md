# Egregore Roadmap

## V0.5: Browser Runtime 🔄

**Goal**: Stable, recoverable browser sessions for all major AI platforms.

### Core Infrastructure
- [ ] Playwright integration (persistent contexts)
- [ ] Session Manager (long-lived browser workers)
- [ ] Browser Pool (resource management)
- [ ] Page Pool (page reuse)

### Executor System
- [ ] BaseExecutor interface (domain port)
- [ ] ChatGPTExecutor
- [ ] ClaudeExecutor
- [ ] GeminiExecutor
- [ ] DeepSeekExecutor
- [ ] GrokExecutor

### Locator System
- [ ] Locator Repository (centralized selectors)
- [ ] Fallback locator chains
- [ ] Locator health checks

### Observability
- [ ] Stream Parser (per-provider)
- [ ] Health Monitor
- [ ] Recovery System (auto-retry with escalation)
- [ ] Event emission for all lifecycle events

### Persistence
- [ ] Cookie/storage state persistence
- [ ] Session metadata storage
- [ ] Recovery state tracking

## V1: Multi-LLM Round Table ✅

**Goal**: Ask a question, get responses from multiple LLMs, see them side by side.

- [x] Project scaffolding (backend + frontend)
- [x] Hexagonal architecture
- [x] Event bus
- [x] Provider abstraction (BaseProvider — API-based)
- [x] Mock provider for development
- [x] OpenAI provider adapter
- [x] Anthropic provider adapter
- [x] Provider registry
- [x] Round table orchestrator (parallel dispatch)
- [x] FastAPI REST API
- [x] Three-column frontend layout

## V1.5: Consensus Engine

**Goal**: Detect agreements, contradictions, and synthesize a unified answer.

- [ ] Semantic similarity analysis
- [ ] Agreement detection
- [ ] Contradiction detection
- [ ] Confidence scoring
- [ ] Summary generation

## V2: Debate Engine

**Goal**: Models can review and critique each other's responses.

- [ ] Critic agents
- [ ] Reflection rounds
- [ ] Revision agents
- [ ] Debate moderator

## V3: Dynamic Weighting

**Goal**: Route questions to the best provider based on domain expertise.

- [ ] Domain specialization tracking
- [ ] ELO rating system
- [ ] Trust scores
- [ ] Adaptive routing

## V4: Memory System

**Goal**: Persistent context and long-term memory.

- [ ] Vector database integration
- [ ] Long-term memory storage
- [ ] Context window management

## V5: Agent Society

**Goal**: Emergent intelligence from specialized agent collaboration.

- [ ] Multiple specialized agents
- [ ] Hierarchical organization
- [ ] Emergent behavior detection
