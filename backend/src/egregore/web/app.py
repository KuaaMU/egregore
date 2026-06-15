"""Egregore Web UI — minimal, clean, Progressive Disclosure."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from egregore.providers.browser_manager import BrowserManager
from egregore.providers.cdp_transport import BrowserTransport
from egregore.synthesis.store import ResponseStore
from egregore.topic.events import TopicEventStore
from egregore.topic.manager import TopicManager
from egregore.topic.store import TopicStore

logger = structlog.get_logger()

STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = Path.home() / ".egregore" / "topics.db"

PROVIDER_URLS = {
    "chatgpt": "https://chatgpt.com/",
    "grok": "https://grok.com/",
    "kimi": "https://kimi.moonshot.cn/",
    "qwen": "https://tongyi.aliyun.com/qianwen/",
    "doubao": "https://www.doubao.com/",
}


def create_web_app() -> FastAPI:
    app = FastAPI(title="Egregore", version="0.5.2")

    store = TopicStore(DB_PATH)
    event_store = TopicEventStore(store._conn)
    response_store = ResponseStore()
    browser_manager = BrowserManager()
    transport = BrowserTransport(browser_manager)
    manager = TopicManager(transport, store, event_store, browser_manager, response_store)

    @app.on_event("startup")
    async def startup():
        try:
            await browser_manager.connect()
        except Exception as e:
            logger.warning("browser_connect_failed", error=str(e))

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
            "urls": t.urls,
            "pinned": t.pinned,
            "last_accessed": t.last_accessed.isoformat(),
        } for t in topics]

    @app.post("/api/topics")
    async def create_topic(body: dict):
        title = body.get("title", "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title is required")
        providers = body.get("providers", [])
        if not providers:
            raise HTTPException(status_code=400, detail="At least one provider is required")
        topic = await manager.create(title, providers)
        return {"id": topic.id, "title": topic.title, "providers": topic.providers, "urls": topic.urls}

    @app.post("/api/topics/{topic_id}/send")
    async def send_prompt(topic_id: str, body: dict):
        prompt = body.get("prompt", "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")

        topic = store.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        try:
            await manager.reopen(topic_id)
        except Exception:
            pass

        async def event_stream():
            url_updates = {}

            async def send_one(provider: str):
                url = topic.get_url(provider) or PROVIDER_URLS.get(provider, "")
                try:
                    page = await browser_manager.get_page(url)
                    old_response = await transport._extract_latest_response(page)
                    old_content_len = await transport._get_content_length(page)

                    input_el = page.get_by_role("textbox").first
                    await input_el.wait_for(state="visible", timeout=10000)
                    await input_el.click()
                    await asyncio.sleep(0.2)
                    await page.keyboard.press("Control+a")
                    await page.keyboard.type(prompt, delay=10)
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Enter")

                    content = await transport._wait_for_response(page, 60000, old_response, old_content_len)

                    new_url = page.url
                    if new_url and new_url != url and ("/c/" in new_url or "/chat/" in new_url):
                        url_updates[provider] = new_url

                    return {"provider": provider, "content": content, "success": len(content) > 0, "images": [], "latency_ms": 0}
                except Exception as e:
                    return {"provider": provider, "content": "", "success": False, "error": str(e), "images": [], "latency_ms": 0}

            tasks = {asyncio.create_task(send_one(p)): p for p in topic.providers}
            completed = []

            for coro in asyncio.as_completed(tasks):
                result = await coro
                completed.append(result)
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

            for provider, new_url in url_updates.items():
                topic.set_url(provider, new_url)

            response_dict = {r["provider"]: r["content"] for r in completed if r["success"]}
            if response_dict:
                response_store.save(topic_id, prompt, response_dict)

            topic.touch()
            store.save(topic)

            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/topics/{topic_id}/close")
    async def close_topic(topic_id: str):
        topic = store.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        await manager.close(topic_id)
        return {"closed": topic_id}

    @app.post("/api/topics/{topic_id}/reopen")
    async def reopen_topic(topic_id: str):
        topic = store.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        topic = await manager.reopen(topic_id)
        return {"id": topic.id, "title": topic.title, "urls": topic.urls}

    @app.delete("/api/topics/{topic_id}")
    async def delete_topic(topic_id: str):
        topic = store.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        try:
            await manager.close(topic_id)
        except Exception:
            pass
        manager.delete_topic(topic_id)
        return {"deleted": topic_id}

    @app.get("/api/topics/{topic_id}/events")
    async def get_events(topic_id: str):
        topic = store.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        return event_store.get_events(topic_id, limit=50)

    @app.get("/api/topics/{topic_id}/responses")
    async def get_responses(topic_id: str):
        topic = store.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        return response_store.load(topic_id)

    return app
