"""Egregore CLI — thin adapter over TopicManager.

No business logic here. Just:
    argv → TopicManager → stdout

Usage:
    uv run python -m egregore.cli create "Redis Cache" --providers chatgpt grok kimi
    uv run python -m egregore.cli list
    uv run python -m egregore.cli send <topic_id> "How does Redis cache work?"
    uv run python -m egregore.cli close <topic_id>
    uv run python -m egregore.cli reopen <topic_id>
    uv run python -m egregore.cli events <topic_id>
    uv run python -m egregore.cli stats <topic_id>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from egregore.providers.browser_manager import BrowserManager
from egregore.providers.cdp_transport import CdpTransport
from egregore.topic.events import TopicEventStore
from egregore.topic.manager import TopicManager
from egregore.topic.store import TopicStore

DB_PATH = Path.home() / ".egregore" / "topics.db"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="egregore", description="Egregore — Topic Runtime CLI")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Create a new topic")
    p_create.add_argument("title", help="Topic title")
    p_create.add_argument("--providers", nargs="+", default=["chatgpt", "grok", "kimi"], help="Provider names")

    # list
    sub.add_parser("list", help="List all topics")

    # send
    p_send = sub.add_parser("send", help="Send a prompt to a topic")
    p_send.add_argument("topic_id", help="Topic ID")
    p_send.add_argument("prompt", help="Prompt text")
    p_send.add_argument("--timeout", type=int, default=60000, help="Timeout in ms")

    # close
    p_close = sub.add_parser("close", help="Close a topic's pages")
    p_close.add_argument("topic_id", help="Topic ID")

    # reopen
    p_reopen = sub.add_parser("reopen", help="Reopen a topic from saved URLs")
    p_reopen.add_argument("topic_id", help="Topic ID")

    # events
    p_events = sub.add_parser("events", help="Show events for a topic")
    p_events.add_argument("topic_id", help="Topic ID")
    p_events.add_argument("--limit", type=int, default=20, help="Max events to show")

    # stats
    p_stats = sub.add_parser("stats", help="Show stats for a topic")
    p_stats.add_argument("topic_id", help="Topic ID")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a topic")
    p_delete.add_argument("topic_id", help="Topic ID")

    return parser


async def run(args: argparse.Namespace) -> None:
    transport = CdpTransport()
    store = TopicStore(DB_PATH)
    event_store = TopicEventStore(store._conn)
    browser_manager = BrowserManager()
    manager = TopicManager(transport, store, event_store, browser_manager)

    try:
        await transport.connect()

        if args.command == "create":
            topic = await manager.create(args.title, args.providers)
            print(f"Topic created")
            print(f"  id:        {topic.id}")
            print(f"  title:     {topic.title}")
            print(f"  providers: {', '.join(topic.providers)}")
            for p, url in topic.urls.items():
                print(f"  {p}: {url}")

        elif args.command == "list":
            topics = manager.list_topics()
            if not topics:
                print("No topics found.")
            else:
                for t in topics:
                    pin = "📌 " if t.pinned else "   "
                    providers = ", ".join(t.providers) if t.providers else "none"
                    print(f"{pin}{t.id}  {t.title}  [{providers}]")

        elif args.command == "send":
            print(f"Sending to {args.topic_id}...")
            results = await manager.send(args.topic_id, args.prompt, args.timeout)
            for r in results:
                status = "OK" if r.success else "FAIL"
                print(f"\n[{r.provider}] {status} ({r.latency_ms:.0f}ms)")
                if r.success:
                    print(f"  {r.content[:300]}")
                else:
                    print(f"  Error: {r.content}")

        elif args.command == "close":
            await manager.close(args.topic_id)
            print(f"Topic {args.topic_id} closed.")

        elif args.command == "reopen":
            topic = await manager.reopen(args.topic_id)
            print(f"Topic {args.topic_id} reopened.")
            for p in topic.providers:
                print(f"  {p}: {topic.get_url(p)}")

        elif args.command == "events":
            events = event_store.get_events(args.topic_id, args.limit)
            if not events:
                print("No events found.")
            else:
                for e in events:
                    provider = f" [{e['provider']}]" if e['provider'] else ""
                    detail = f" — {e['detail'][:60]}" if e['detail'] else ""
                    print(f"  {e['timestamp'][:19]}  {e['event_type']}{provider}{detail}")

        elif args.command == "stats":
            stats = manager.get_topic_stats(args.topic_id)
            if not stats:
                print("No stats found.")
            else:
                print(f"Stats for {args.topic_id}:")
                for k, v in stats.items():
                    print(f"  {k}: {v}")

        elif args.command == "delete":
            manager.delete_topic(args.topic_id)
            print(f"Topic {args.topic_id} deleted.")

        else:
            print("Unknown command. Use --help for usage.")

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
