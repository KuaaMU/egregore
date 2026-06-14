"""Egregore Local Daemon — receives messages from browser extension.

Run: python daemon.py

This is a simple WebSocket server that the extension connects to.
It receives prompts and responses from the browser extension.

Architecture:
    Chrome Extension → WebSocket → This Daemon → Egregore API

Status: POC — just receives and prints messages.
"""

import asyncio
import json

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets")
    exit(1)


async def handler(websocket):
    """Handle messages from the extension."""
    print(f"[Daemon] Extension connected: {websocket.remote_address}")

    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "send":
                print(f"[Daemon] Prompt to {data.get('platform')}: {data.get('prompt')[:100]}")

            elif msg_type == "response":
                print(f"[Daemon] Response from {data.get('platform')}: {data.get('content')[:100]}")

            else:
                print(f"[Daemon] Unknown message: {data}")

    except websockets.exceptions.ConnectionClosed:
        print("[Daemon] Extension disconnected")


async def main():
    print("[Daemon] Starting Egregore daemon on ws://localhost:8765")
    async with websockets.serve(handler, "localhost", 8765):
        print("[Daemon] Ready. Install the extension and open ChatGPT.")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
