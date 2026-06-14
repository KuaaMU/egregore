"""Egregore Web UI — minimal, clean, Progressive Disclosure."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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
    app = FastAPI(title="Egregore", version="0.4.0")

    store = TopicStore(DB_PATH)
    event_store = TopicEventStore(store._conn)
    response_store = ResponseStore()
    transport = CdpTransport()
    browser_manager = transport._browser_manager
    manager = TopicManager(transport, store, event_store, browser_manager, response_store)

    @app.on_event("startup")
    async def startup():
        await ensure_browser()
        transport._browser_manager._browser = None
        transport._browser_manager._playwright = None
        await transport.connect()

    @app.on_event("shutdown")
    async def shutdown():
        await transport.close()
        store.close()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

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

        # Auto-reopen if needed
        try:
            await manager.reopen(topic_id)
        except Exception:
            pass

        # Get topic info
        topic = store.get(topic_id)
        if not topic:
            return {"error": "Topic not found"}

        # Send to ALL providers in parallel
        from egregore.providers.cdp_transport import CdpTransport

        async def send_one(provider: str):
            url = topic.get_url(provider) or ""
            try:
                page = await transport._browser_manager.get_page(url)
                old_response = await transport._extract_latest_response(page)
                old_content_len = await transport._get_content_length(page)

                # Type and send
                input_el = page.get_by_role("textbox").first
                await input_el.wait_for(state="visible", timeout=10000)
                await input_el.click()
                await asyncio.sleep(0.2)
                await page.keyboard.press("Control+a")
                await page.keyboard.type(prompt, delay=10)
                await asyncio.sleep(0.3)
                await page.keyboard.press("Enter")

                # Wait for response
                content = await transport._wait_for_response(page, 60000, old_response, old_content_len)

                # Detect images
                images = []
                try:
                    imgs = page.locator("img[src*='dalle'], img[src*='generated'], img[alt*='generated']")
                    count = await imgs.count()
                    for i in range(min(count, 5)):
                        src = await imgs.nth(i).get_attribute("src")
                        if src:
                            images.append(src)
                except Exception:
                    pass

                return {
                    "provider": provider,
                    "content": content,
                    "success": len(content) > 0,
                    "images": images,
                }
            except Exception as e:
                return {"provider": provider, "content": "", "success": False, "error": str(e), "images": []}

        # Run all providers in parallel
        tasks = [send_one(p) for p in topic.providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed = []
        for r in results:
            if isinstance(r, Exception):
                processed.append({"provider": "unknown", "content": "", "success": False, "error": str(r), "images": []})
            else:
                processed.append(r)

        # Save responses
        response_dict = {r["provider"]: r["content"] for r in processed if r["success"]}
        if response_dict:
            response_store.save(topic_id, prompt, response_dict)

        # Update topic access time
        topic.touch()
        store.save(topic)

        return processed

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
        return event_store.get_events(topic_id, limit=50)

    @app.get("/api/topics/{topic_id}/responses")
    async def get_responses(topic_id: str):
        return response_store.load(topic_id)

    return app
