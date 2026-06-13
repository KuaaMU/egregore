# Egregore Roadmap

## V1: Multi-LLM Round Table ✅

**Goal**: Ask a question, get responses from multiple LLMs, see them side by side.

- [x] Project scaffolding (backend + frontend)
- [x] Hexagonal architecture
- [x] Event bus
- [x] Provider abstraction (BaseProvider)
- [x] Mock provider for development
- [x] OpenAI provider adapter
- [x] Anthropic provider adapter
- [x] Provider registry
- [x] Round table orchestrator (parallel dispatch)
- [x] FastAPI REST API
- [x] Three-column frontend layout
- [x] Provider response cards with latency badges

**Next**:
- [ ] Streaming support (SSE / WebSocket)
- [ ] API key configuration UI
- [ ] Error handling and retry logic

## V2: Consensus Engine

**Goal**: Detect agreements, contradictions, and synthesize a unified answer.

- [ ] Semantic similarity analysis
- [ ] Agreement detection
- [ ] Contradiction detection
- [ ] Confidence scoring
- [ ] Summary generation (local Ollama / Qwen3)

## V3: Debate Engine

**Goal**: Models can review and critique each other's responses.

- [ ] Critic agents
- [ ] Reflection rounds
- [ ] Revision agents
- [ ] Debate moderator

## V4: Dynamic Weighting

**Goal**: Route questions to the best provider based on domain expertise.

- [ ] Domain specialization tracking
- [ ] ELO rating system
- [ ] Trust scores
- [ ] Adaptive routing

## V5: Memory System

**Goal**: Persistent context and long-term memory.

- [ ] Vector database integration
- [ ] Long-term memory storage
- [ ] Context window management
- [ ] LangGraph integration

## V6: Agent Society

**Goal**: Emergent intelligence from specialized agent collaboration.

- [ ] Multiple specialized agents
- [ ] Hierarchical organization
- [ ] Emergent behavior detection
- [ ] Distributed cognition patterns
