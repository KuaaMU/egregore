"""Egregore CLI — optimized for humans and agents.

Usage:
    # Create
    egregore create "Redis Cache" --providers chatgpt grok

    # Send (by title)
    egregore send "Redis Cache" "How does Redis cache work?"

    # Send (last topic)
    egregore send "How does Redis cache work?"

    # List
    egregore list
    egregore list --json

    # Close / Reopen / Delete (by title or ID)
    egregore close "Redis Cache"
    egregore reopen "Redis Cache"

    # Events / Stats
    egregore events "Redis Cache"
    egregore stats "Redis Cache" --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from egregore.providers.bootstrap import ensure_browser
from egregore.providers.cdp_transport import CdpTransport
from egregore.topic.events import TopicEventStore
from egregore.topic.manager import TopicManager
from egregore.topic.models import Topic
from egregore.topic.store import TopicStore

DB_PATH = Path.home() / ".egregore" / "topics.db"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="egregore",
        description="Egregore — Topic Runtime for Collective Intelligence",
    )
    sub = parser.add_subparsers(dest="command")

    def add_json_flag(p):
        p.add_argument("--json", action="store_true", help="JSON output")

    # create
    p = sub.add_parser("create", help="Create a new topic")
    p.add_argument("title", help="Topic title")
    p.add_argument("--providers", nargs="+", default=["chatgpt", "grok", "kimi"])
    add_json_flag(p)

    # list
    p = sub.add_parser("list", help="List all topics")
    add_json_flag(p)

    # send
    p = sub.add_parser("send", help="Send a prompt")
    p.add_argument("topic_or_prompt", nargs="?", help="Topic title/ID or prompt")
    p.add_argument("prompt", nargs="?", help="Prompt text")
    p.add_argument("--timeout", type=int, default=60000)
    add_json_flag(p)

    # close
    p = sub.add_parser("close", help="Close a topic")
    p.add_argument("topic", nargs="?", help="Topic title/ID")
    add_json_flag(p)

    # reopen
    p = sub.add_parser("reopen", help="Reopen a topic")
    p.add_argument("topic", nargs="?", help="Topic title/ID")
    add_json_flag(p)

    # events
    p = sub.add_parser("events", help="Show events")
    p.add_argument("topic", nargs="?", help="Topic title/ID")
    p.add_argument("--limit", type=int, default=20)
    add_json_flag(p)

    # stats
    p = sub.add_parser("stats", help="Show stats")
    p.add_argument("topic", nargs="?", help="Topic title/ID")
    add_json_flag(p)

    # delete
    p = sub.add_parser("delete", help="Delete a topic")
    p.add_argument("topic", nargs="?", help="Topic title/ID")
    add_json_flag(p)

    return parser


def resolve_topic(store: TopicStore, identifier: str | None) -> Topic | None:
    """Resolve a topic by title, ID prefix, or None (last topic)."""
    topics = store.list_all()
    if not topics:
        return None

    if identifier is None:
        return topics[0]

    # Exact ID
    for t in topics:
        if t.id == identifier:
            return t

    # ID prefix
    matches = [t for t in topics if t.id.startswith(identifier)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous ID '{identifier}': {[t.id for t in matches]}", file=sys.stderr)
        return None

    # Exact title
    matches = [t for t in topics if t.title.lower() == identifier.lower()]
    if len(matches) == 1:
        return matches[0]

    # Partial title
    matches = [t for t in topics if identifier.lower() in t.title.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous title '{identifier}': {[t.title for t in matches]}", file=sys.stderr)
        return None

    print(f"Topic '{identifier}' not found.", file=sys.stderr)
    return None


def topic_to_dict(t: Topic) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "providers": t.providers,
        "urls": t.urls,
        "pinned": t.pinned,
        "created_at": t.created_at.isoformat(),
        "last_accessed": t.last_accessed.isoformat(),
    }


def get_json_flag(args) -> bool:
    return getattr(args, "json", False)


async def run(args: argparse.Namespace) -> None:
    use_json = get_json_flag(args)
    store = TopicStore(DB_PATH)
    event_store = TopicEventStore(store._conn)

    # === Commands that don't need CDP ===

    if args.command == "list":
        topics = store.list_all()
        if use_json:
            print(json.dumps([topic_to_dict(t) for t in topics], ensure_ascii=False))
        else:
            if not topics:
                print("No topics.")
            else:
                for t in topics:
                    pin = " *" if t.pinned else ""
                    providers = ", ".join(t.providers)
                    print(f"  {t.id}  {t.title}{pin}  [{providers}]")
        store.close()
        return

    if args.command == "events":
        topic = resolve_topic(store, args.topic)
        if topic:
            events = event_store.get_events(topic.id, args.limit)
            if use_json:
                print(json.dumps(events, ensure_ascii=False, default=str))
            else:
                if not events:
                    print("No events.")
                else:
                    for e in events:
                        prov = f" [{e['provider']}]" if e['provider'] else ""
                        detail = f" — {e['detail'][:50]}" if e['detail'] else ""
                        print(f"  {e['timestamp'][:19]}  {e['event_type']}{prov}{detail}")
        store.close()
        return

    if args.command == "stats":
        topic = resolve_topic(store, args.topic)
        if topic:
            stats = event_store.get_stats(topic.id)
            if use_json:
                print(json.dumps(stats, ensure_ascii=False))
            else:
                print(f"Stats for {topic.title}:")
                for k, v in stats.items():
                    print(f"  {k}: {v}")
        store.close()
        return

    # === Commands that need CDP ===

    # Auto-start browser if needed
    try:
        await ensure_browser()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        store.close()
        return

    transport = CdpTransport()
    browser_manager = transport._browser_manager
    manager = TopicManager(transport, store, event_store, browser_manager)

    try:
        await transport.connect()

        if args.command == "create":
            topic = await manager.create(args.title, args.providers)
            if use_json:
                print(json.dumps(topic_to_dict(topic), ensure_ascii=False))
            else:
                print(f"Created: {topic.title}")
                print(f"  ID: {topic.id}")
                for p in topic.providers:
                    print(f"  {p}: {topic.get_url(p)}")

        elif args.command == "send":
            if args.prompt is not None:
                topic_id = args.topic_or_prompt
                prompt = args.prompt
            else:
                topic_id = None
                prompt = args.topic_or_prompt

            if not prompt:
                print("Error: No prompt.", file=sys.stderr)
                return

            topic = resolve_topic(store, topic_id)
            if not topic:
                return

            await manager.reopen(topic.id)
            results = await manager.send(topic.id, prompt, args.timeout)

            if use_json:
                out = [{"provider": r.provider, "content": r.content, "success": r.success, "latency_ms": r.latency_ms} for r in results]
                print(json.dumps(out, ensure_ascii=False))
            else:
                for r in results:
                    status = "OK" if r.success else "FAIL"
                    print(f"\n[{r.provider}] {status} ({r.latency_ms:.0f}ms)")
                    if r.success:
                        print(f"  {r.content[:300]}")
                    else:
                        print(f"  Error")

        elif args.command == "close":
            topic = resolve_topic(store, args.topic)
            if topic:
                await manager.close(topic.id)
                if use_json:
                    print(json.dumps({"closed": topic.id}))
                else:
                    print(f"Closed: {topic.title}")

        elif args.command == "reopen":
            topic = resolve_topic(store, args.topic)
            if topic:
                await manager.reopen(topic.id)
                if use_json:
                    print(json.dumps(topic_to_dict(topic)))
                else:
                    print(f"Reopened: {topic.title}")
                    for p in topic.providers:
                        print(f"  {p}: {topic.get_url(p)}")

        elif args.command == "delete":
            topic = resolve_topic(store, args.topic)
            if topic:
                manager.delete_topic(topic.id)
                if use_json:
                    print(json.dumps({"deleted": topic.id}))
                else:
                    print(f"Deleted: {topic.title}")

        else:
            print("Unknown command. Use --help.")

    finally:
        await transport.close()
        store.close()


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
