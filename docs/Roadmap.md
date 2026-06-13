# Egregore Roadmap

**Revised**: 2026-06-13 (Transport-First)

> Users don't buy architectures. They buy lower cost and convenience.
> Without reliable transport, nothing else matters.

---

## V0.8: ChatGPT Browser Adapter 🔄

**Goal**: Prove Egregore can reliably talk to a real AI platform.

**Success criteria**: 24h runtime, 95% success rate.

- [x] ChatGPT Browser Adapter (Playwright persistent context)
- [x] Simple send() / health_check() / close()
- [x] Reliability test runner
- [ ] First manual login + session save
- [ ] 24h reliability test
- [ ] Selector verification against live ChatGPT UI

**Run**:
```bash
# First run (non-headless, manual login)
uv run python -m egregore.labs.transport.test_chatgpt

# Reliability test (headless, 24h)
uv run python -m egregore.labs.transport.reliability 24 300
```

## V0.9: Claude Browser Adapter

**Goal**: Second platform proves the pattern is reusable.

- [ ] Claude Browser Adapter
- [ ] 24h reliability test
- [ ] Login state persistence

## V1: Round Table

**Goal**: Parallel dispatch to multiple providers.

- [ ] Round Table Orchestrator (already built)
- [ ] API providers (OpenAI, Anthropic — already built)
- [ ] Browser providers (ChatGPT, Claude)
- [ ] Three-column UI

## V1.1: Synthesis Engine

**Goal**: Prove collective intelligence works.

- [ ] Synthesis Engine (already built)
- [ ] Benchmark: Synthesis > Best Individual > 70%
- [ ] 12 benchmark cases across 7 domains

## V1.5: Critic Engine

**Goal**: Review and improve synthesis.

- [ ] Critic agent reviews synthesis
- [ ] Refined answer

## V2: Dynamic Weighting

**Goal**: Route to best provider based on domain.

- [ ] ELO rating
- [ ] Trust scores
- [ ] Adaptive routing

## V3: Memory

**Goal**: Persistent context across sessions.

- [ ] Vector database
- [ ] Long-term memory

## V4: Debate

**Goal**: Models critique each other.

- [ ] Multi-round debate
- [ ] Debate transcript

## V5: Agent Society

**Goal**: Emergent intelligence.

- [ ] Specialized agents
- [ ] Hierarchical organization

---

## Deferred (not building)

- ❌ Browser Pool / Distributed Runtime
- ❌ Cloud Browser
- ❌ Complex Recovery State Machine
- ❌ Per-platform browser executors (use simple adapters)
