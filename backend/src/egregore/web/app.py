"""Egregore Web UI — minimal, clean, Progressive Disclosure."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from egregore.providers.bootstrap import ensure_browser
from egregore.providers.cdp_transport import CdpTransport
from egregore.synthesis.store import ResponseStore
from egregore.topic.events import TopicEventStore
from egregore.topic.manager import TopicManager
from egregore.topic.store import TopicStore

STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = Path.home() / ".egregore" / "topics.db"


def create_web_app() -> FastAPI:
    app = FastAPI(title="Egregore", version="0.5.1")

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
            "urls": t.urls,
            "pinned": t.pinned,
            "last_accessed": t.last_accessed.isoformat(),
        } for t in topics]

    @app.post("/api/topics")
    async def create_topic(body: dict):
        title = body.get("title", "Untitled")
        providers = body.get("providers", ["chatgpt", "grok"])
        topic = await manager.create(title, providers)
        return {"id": topic.id, "title": topic.title, "providers": topic.providers, "urls": topic.urls}

    @app.post("/api/topics/{topic_id}/send")
    async def send_prompt(topic_id: str, body: dict):
        """SSE endpoint: streams results as each provider responds."""
        prompt = body.get("prompt", "")
        if not prompt:
            return {"error": "No prompt"}

        # Auto-reopen
        try:
            await manager.reopen(topic_id)
        except Exception:
            pass

        topic = store.get(topic_id)
        if not topic:
            return {"error": "Topic not found"}

        PROVIDER_URLS = {
            "chatgpt": "https://chatgpt.com/",
            "grok": "https://grok.com/",
            "kimi": "https://kimi.moonshot.cn/",
            "qwen": "https://tongyi.aliyun.com/qianwen/",
            "doubao": "https://www.doubao.com/",
        }

        async def event_stream():
            url_updates = {}

            async def send_one(provider: str):
                url = topic.get_url(provider) or PROVIDER_URLS.get(provider, "")
                try:
                    page = await transport._browser_manager.get_page(url)
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

                    # Capture conversation URL after sending
                    new_url = page.url
                    if new_url and new_url != url and "/c/" in new_url or "/chat/" in new_url:
                        url_updates[provider] = new_url

                    images = []
                    try:
                        imgs = page.locator("img[src*='dalle'], img[src*='generated'], img[src*='blob:']")
                        count = await imgs.count()
                        for i in range(min(count, 5)):
                            src = await imgs.nth(i).get_attribute("src")
                            if src:
                                images.append(src)
                    except Exception:
                        pass

                    return {"provider": provider, "content": content, "success": len(content) > 0, "images": images, "latency_ms": 0}
                except Exception as e:
                    return {"provider": provider, "content": "", "success": False, "error": str(e), "images": [], "latency_ms": 0}

            # Send all in parallel, stream results as they complete
            tasks = {asyncio.create_task(send_one(p)): p for p in topic.providers}
            completed = []

            for coro in asyncio.as_completed(tasks):
                result = await coro
                completed.append(result)
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

            # Save URL updates
            for provider, new_url in url_updates.items():
                topic.set_url(provider, new_url)

            # Save all responses
            response_dict = {r["provider"]: r["content"] for r in completed if r["success"]}
            if response_dict:
                response_store.save(topic_id, prompt, response_dict)

            topic.touch()
            store.save(topic)

            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/topics/{topic_id}/close")
    async def close_topic(topic_id: str):
        await manager.close(topic_id)
        return {"closed": topic_id}

    @app.post("/api/topics/{topic_id}/reopen")
    async def reopen_topic(topic_id: str):
        topic = await manager.reopen(topic_id)
        return {"id": topic.id, "title": topic.title, "urls": topic.urls}

    @app.delete("/api/topics/{topic_id}")
    async def delete_topic(topic_id: str):
        # Close runtime first
        try:
            await manager.close(topic_id)
        except Exception:
            pass
        # Delete from store
        manager.delete_topic(topic_id)
        return {"deleted": topic_id}

    @app.get("/api/topics/{topic_id}/events")
    async def get_events(topic_id: str):
        return event_store.get_events(topic_id, limit=50)

    @app.get("/api/topics/{topic_id}/responses")
    async def get_responses(topic_id: str):
        return response_store.load(topic_id)

    def _provider_url(provider: str) -> str:
        urls = {
            "chatgpt": "https://chatgpt.com/",
            "grok": "https://grok.com/",
            "kimi": "https://kimi.moonshot.cn/",
            "qwen": "https://tongyi.aliyun.com/qianwen/",
            "doubao": "https://www.doubao.com/",
        }
        return urls.get(provider, "")

    return app
