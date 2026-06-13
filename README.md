# ⬡ Egregore

**Where Intelligence Emerges Together**

Egregore is a platform for collective intelligence and emergent reasoning. It explores multi-LLM collaboration, consensus formation, debate between models, and agent societies.

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Backend

```bash
cd backend
uv sync
uv run python -m egregore
```

The API will be available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:3000`.

### With Real Providers

Create a `.env` file in the backend directory:

```env
EGREGORE_OPENAI_API_KEY=sk-...
EGREGORE_ANTHROPIC_API_KEY=sk-ant-...
```

Without API keys, Egregore runs with mock providers for development.

## Architecture

Egregore follows Hexagonal Architecture (Ports & Adapters):

- **Domain**: Entities and provider abstractions
- **Application**: Orchestrators (round table flow)
- **Infrastructure**: Provider adapters (OpenAI, Anthropic, Mock)
- **API**: FastAPI routes and schemas

See [docs/Architecture.md](docs/Architecture.md) for details.

## Roadmap

| Version | Feature |
|---------|---------|
| V1 | Multi-LLM Round Table |
| V2 | Consensus Engine |
| V3 | Debate Engine |
| V4 | Dynamic Weighting |
| V5 | Memory System |
| V6 | Agent Society |

See [docs/Roadmap.md](docs/Roadmap.md) for details.

## Project Structure

```
Egregore/
├── backend/
│   └── src/egregore/
│       ├── api/            # FastAPI routes, schemas
│       ├── application/    # Orchestrators, services
│       ├── config/         # Settings
│       ├── domain/         # Entities, ports, events
│       └── infrastructure/ # Provider adapters
├── frontend/
│   └── src/
│       ├── app/            # Next.js pages
│       ├── components/     # React components
│       └── types/          # TypeScript types
└── docs/
    ├── ADR/                # Architecture Decision Records
    ├── Architecture.md
    └── Roadmap.md
```

## License

MIT
