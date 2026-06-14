"""Egregore Web UI — minimal, clean, Progressive Disclosure.

Architecture:
    FastAPI → REST API → TopicManager → Providers
    Static HTML → fetch() → REST API

No framework. No React. Just HTML + CSS + fetch().
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from egregore.providers.bootstrap import ensure_browser
from egregore.providers.cdp_transport import CdpTransport
from egregore.synthesis.store import ResponseStore
from egregore.topic.events import TopicEventStore
from egregore.topic.manager import TopicManager
from egregore.topic.store import TopicStore

STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = Path.home() / ".egregore" / "topics.db"


def create_web_app() -> FastAPI:
    """Create the Egregore web application."""
    app = FastAPI(title="Egregore", version="0.4.0")

    # Shared state
    store = TopicStore(DB_PATH)
    event_store = TopicEventStore(store._conn)
    response_store = ResponseStore()
    transport = CdpTransport()
    browser_manager = transport._browser_manager
    manager = TopicManager(transport, store, event_store, browser_manager, response_store)

    @app.on_event("startup")
    async def startup():
        await ensure_browser()
        # Force reconnect (bootstrap may have restarted Chrome)
        transport._browser_manager._browser = None
        transport._browser_manager._playwright = None
        await transport.connect()

    @app.on_event("shutdown")
    async def shutdown():
        await transport.close()
        store.close()

    # === Pages ===

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    # === API ===

    @app.get("/api/topics")
    async def list_topics():
        topics = manager.list_topics()
        return [{
            "id": t.id,
            "title": t.title,
            "providers": t.providers,
            "pinned": t.pinned,
            "last_accessed": t.last_accessed.isoformat(),
        } for t in topics]

    @app.post("/api/topics")
    async def create_topic(body: dict):
        title = body.get("title", "Untitled")
        providers = body.get("providers", ["chatgpt", "grok"])
        topic = await manager.create(title, providers)
        return {"id": topic.id, "title": topic.title, "providers": topic.providers}

    @app.post("/api/topics/{topic_id}/send")
    async def send_prompt(topic_id: str, body: dict):
        prompt = body.get("prompt", "")
        if not prompt:
            return {"error": "No prompt"}
        results = await manager.send(topic_id, prompt, timeout_ms=60000)
        return [{
            "provider": r.provider,
            "content": r.content,
            "success": r.success,
            "latency_ms": r.latency_ms,
        } for r in results]

    @app.post("/api/topics/{topic_id}/close")
    async def close_topic(topic_id: str):
        await manager.close(topic_id)
        return {"closed": topic_id}

    @app.post("/api/topics/{topic_id}/reopen")
    async def reopen_topic(topic_id: str):
        topic = await manager.reopen(topic_id)
        return {"id": topic.id, "title": topic.title}

    @app.delete("/api/topics/{topic_id}")
    async def delete_topic(topic_id: str):
        manager.delete_topic(topic_id)
        return {"deleted": topic_id}

    @app.get("/api/topics/{topic_id}/events")
    async def get_events(topic_id: str):
        events = event_store.get_events(topic_id, limit=50)
        return events

    @app.get("/api/topics/{topic_id}/responses")
    async def get_responses(topic_id: str):
        return response_store.load(topic_id)

    return app
