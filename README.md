# ⬡ Egregore

**A Topic Runtime for Collective Intelligence**

Egregore is not a chatbot. It's not another ChatGPT client. It's a runtime that lets you manage conversations across multiple AI platforms from a single interface.

```
Topic: "Redis Cache Architecture"
├── ChatGPT:  https://chatgpt.com/c/xxx
├── Grok:     https://grok.com/chat/xxx
├── Kimi:     https://kimi.moonshot.cn/chat/xxx
├── Qwen:     https://tongyi.aliyun.com/qianwen/xxx
└── Doubao:   https://www.doubao.com/chat/xxx
```

## Quick Start

### Prerequisites

- Python 3.13+
- Chrome or Edge (with remote debugging)
- [uv](https://docs.astral.sh/uv/)

### Setup

```bash
# Clone
git clone https://github.com/KuaaMU/egregore.git
cd egregore/backend

# Install
uv sync

# Start Chrome with remote debugging
# Close ALL Chrome windows first, then:
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

# Login to ChatGPT, Grok, Kimi, etc. in that Chrome
```

### Usage

```bash
# Create a topic
uv run python -m egregore create "Redis Cache" --providers chatgpt grok kimi

# Send a prompt
uv run python -m egregore send <topic_id> "How does Redis cache work?"

# List topics
uv run python -m egregore list

# Close a topic (frees browser tabs, keeps metadata)
uv run python -m egregore close <topic_id>

# Reopen a topic (restores tabs from saved URLs)
uv run python -m egregore reopen <topic_id>

# View events
uv run python -m egregore events <topic_id>

# View stats
uv run python -m egregore stats <topic_id>

# Delete a topic
uv run python -m egregore delete <topic_id>
```

## Architecture

```
providers/
├── base.py              # Provider Protocol
├── transport.py         # Transport Protocol
├── cdp_transport.py     # Chrome CDP implementation
├── browser_manager.py   # Page pool, reuse tabs
├── network_observer.py  # Intercept network for metadata
├── metrics.py           # ProviderMetrics
└── {chatgpt,grok,kimi,qwen,doubao}/

topic/
├── models.py            # Topic entity
├── store.py             # SQLite metadata storage
├── events.py            # Event log
├── runtime.py           # TopicRuntime (in-memory)
└── manager.py           # TopicManager (create/send/close/reopen)

cli/
└── main.py              # Thin CLI adapter
```

### Key Design Decisions

| Decision | Why |
|----------|-----|
| **Topic is the core entity** | Users think in topics, not messages |
| **Shallow cache** | Platforms store content; we store metadata + URLs |
| **CDP Transport** | Attaches to user's Chrome; no headless, no CAPTCHA |
| **Transport abstraction** | Provider doesn't know if it's CDP, Extension, or API |
| **Event log** | Observability before features |

### How It Works

1. **BrowserManager** connects to Chrome via CDP
2. **CdpTransport** sends prompts by typing into web UIs
3. **TopicManager** creates/reuses browser tabs per topic
4. **TopicStore** saves metadata to SQLite (never message content)
5. **TopicEvent** logs every action for observability

### Verified Platforms

| Platform | Status | Latency (p50) |
|----------|--------|---------------|
| ChatGPT | ✅ | 9.1s |
| Grok | ✅ | 14.4s |
| Kimi | ✅ | 10.4s |
| Qwen | ✅ | 7.2s |
| Doubao | ✅ | 4.2s |

## Roadmap

```
Phase 3A: Topic Runtime          ✅
Phase 3B: Observability          ✅
Phase 3C: Runtime Layer          ✅
Phase 3D: CLI + E2E              ✅
Phase 3E: Dogfooding             ← Current (use it daily for 1-2 weeks)
Phase 4:  Round Table            Planned
Phase 5:  Synthesis              Planned
```

## Project Structure

```
Egregore/
├── backend/
│   └── src/egregore/
│       ├── providers/     # Platform connectors
│       ├── topic/         # Topic runtime
│       └── cli/           # CLI
├── extension/             # Chrome extension (research)
├── frontend/              # Next.js (future)
└── docs/
    ├── Architecture.md
    ├── Roadmap.md
    └── ADR/
```

## License

MIT
