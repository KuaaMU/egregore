# ⬡ Egregore

**A Synthesis Engine for Collective Intelligence**

Egregore is not a chatbot. It's a platform that makes multiple AI models collaborate to produce better answers than any single model.

```
User Question
    ↓
ChatGPT + Grok + Kimi + Qwen + Doubao  (via browser extension)
    ↓
Agreement Detection + Contradiction Detection
    ↓
Synthesis → Better Answer
```

## Architecture

```
Chrome Extension (runs in user's browser)
    ↓ WebSocket
Local Daemon (Python)
    ↓
Topic Manager → Synthesis Engine → API/CLI
```

**Key insight**: The extension runs IN the user's browser, sharing cookies and login state. No headless Chrome, no cookie copying, no CAPTCHA.

## Quick Start

### 1. Install Extension

1. Open Chrome → `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" → select `extension/` folder

### 2. Start Daemon

```bash
cd backend
uv sync
uv run python -m egregore.extension.daemon
```

### 3. Use

Open any AI platform (ChatGPT, Grok, etc.) in Chrome. The extension automatically connects to the daemon.

## Project Structure

```
Egregore/
├── extension/              # Chrome extension
│   ├── manifest.json
│   └── src/
│       ├── background.js   # WebSocket to daemon
│       └── platforms/      # Per-platform adapters
│           ├── chatgpt.js
│           ├── grok.js
│           ├── kimi.js
│           ├── qwen.js
│           └── doubao.js
├── backend/                # Python daemon + API
│   └── src/egregore/
│       ├── extension/      # WebSocket daemon
│       ├── topic/          # Topic runtime
│       ├── synthesis/      # Synthesis engine
│       └── providers/      # Provider abstractions
└── frontend/               # Web UI (future)
```

## Roadmap

```
V0.5  Extension + Daemon          ← Current
V1    Round Table (multi-model)
V1.5  Synthesis Engine
V2    Critic Engine
V3    Dynamic Weighting
V4    Memory
V5    Agent Society
```

## License

MIT
