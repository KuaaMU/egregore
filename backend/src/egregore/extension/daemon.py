"""Egregore Extension Daemon — WebSocket server for browser extension.

The extension connects here. Commands flow:
  Python → WebSocket → Extension → Platform DOM
  Platform DOM → Extension → WebSocket → Python

Usage:
    uv run python -m egregore.extension.daemon
"""

from __future__ import annotations

import asyncio
import json

import structlog

logger = structlog.get_logger()

try:
    import websockets
except ImportError:
    print("Install websockets: uv add websockets")
    raise


class ExtensionDaemon:
    """WebSocket server that communicates with the browser extension."""

    def __init__(self, host: str = "localhost", port: int = 9225) -> None:
        self._host = host
        self._port = port
        self._connections: list = []
        self._pending_responses: dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        """Start the WebSocket server."""
        async with websockets.serve(self._handler, self._host, self._port):
            logger.info("extension_daemon_started", host=self._host, port=self._port)
            await asyncio.Future()  # Run forever

    async def _handler(self, websocket) -> None:
        """Handle a single extension connection."""
        self._connections.append(websocket)
        logger.info("extension_connected", address=str(websocket.remote_address))

        try:
            async for message in websocket:
                data = json.loads(message)
                await self._on_message(websocket, data)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._connections.remove(websocket)
            logger.info("extension_disconnected")

    async def _on_message(self, websocket, data: dict) -> None:
        """Handle message from extension."""
        msg_type = data.get("type")

        if msg_type == "response":
            platform = data.get("platform", "")
            content = data.get("content", "")
            url = data.get("url", "")
            conversation_url = data.get("conversationUrl", "")

            logger.info(
                "response_received",
                platform=platform,
                content_length=len(content),
                url=conversation_url,
            )

            # Resolve pending future if any
            future = self._pending_responses.pop(platform, None)
            if future and not future.done():
                future.set_result({
                    "platform": platform,
                    "content": content,
                    "url": conversation_url,
                })

    async def send_prompt(self, platform: str, prompt: str) -> dict:
        """Send a prompt to a platform via the extension.

        Returns the response when complete.
        """
        if not self._connections:
            raise RuntimeError("No extension connected")

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[platform] = future

        # Send command to extension
        message = json.dumps({
            "type": "send_prompt",
            "platform": platform,
            "prompt": prompt,
        })

        for conn in self._connections:
            try:
                await conn.send(message)
            except Exception:
                pass

        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=120)
            return result
        except asyncio.TimeoutError:
            self._pending_responses.pop(platform, None)
            raise RuntimeError(f"Timeout waiting for {platform} response")

    @property
    def is_connected(self) -> bool:
        return len(self._connections) > 0


async def main():
    daemon = ExtensionDaemon()
    print(f"Starting Egregore Extension Daemon on ws://localhost:9225")
    print("Install the Chrome extension and open an AI platform.")
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())
