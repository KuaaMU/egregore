# Egregore Roadmap

**Revised**: 2026-06-13 (Strategic Review)

> The moat is collective intelligence, not browser automation.
> Build synthesis, not infrastructure.

---

## V1: Collective Intelligence MVP 🔄

**Goal**: Prove that multi-model consensus is valuable.

**Success metric**: User asks a question → sees consensus + contradictions that no single model provides.

- [ ] API-based parallel dispatch (OpenAI, Anthropic, OpenRouter)
- [ ] Response collection with metadata (latency, tokens, model)
- [ ] Consensus Engine: detect agreements, contradictions, synthesize
- [ ] Confidence scoring
- [ ] Three-column UI (history, consensus, individual responses)
- [ ] Streaming support (SSE)
- [ ] Provider health (simple: available/unavailable)

## V1.5: Browser Transport (optional)

**Goal**: Add browser-based providers for platforms without APIs.

**Only build if**: A target platform has no API and we need browser access.

- [ ] Playwright persistent context for one provider
- [ ] Basic selector management
- [ ] Simple health check

## V2: Debate Engine

**Goal**: Models review and improve each other.

- [ ] Critic agent (reviews responses for errors, gaps)
- [ ] Revision agent (improves based on critique)
- [ ] Multi-round debate
- [ ] Debate transcript in UI

## V3: Dynamic Weighting

**Goal**: Route questions to the best provider based on domain.

- [ ] Track success rate per provider per domain
- [ ] ELO-style rating system
- [ ] Adaptive routing

## V4: Memory

**Goal**: Persistent context across sessions.

- [ ] Vector database integration
- [ ] Long-term memory storage
- [ ] Context retrieval and relevance scoring

## V5: Agent Society

**Goal**: Emergent intelligence from specialized agents.

- [ ] Specialized agents (researcher, critic, synthesizer)
- [ ] Hierarchical organization
- [ ] Emergent behavior detection

---

## Deferred (may never build)

These were considered but deferred. They are infrastructure, not product:

- ❌ Browser Pool / Distributed Runtime
- ❌ Cloud Browser
- ❌ Per-platform browser executors (ChatGPTExecutor, ClaudeExecutor, ...)
- ❌ Complex recovery escalation system
- ❌ Custom session management (use Playwright built-in)
