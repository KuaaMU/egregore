"""Test ChatGPT via Chrome CDP Connector.

Usage:
    1. Start Chrome with: chrome.exe --remote-debugging-port=9222
    2. Login to ChatGPT in that Chrome
    3. Run: uv run python -m egregore.labs.transport.test_chatgpt
"""

import asyncio
import sys

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTConnector


async def main():
    print("Connecting to Chrome via CDP...")
    connector = ChatGPTConnector()

    try:
        await connector.connect()
        print("[OK] Connected")

        healthy = await connector.health_check()
        print(f"[OK] Health: {'OK' if healthy else 'FAILED'}")

        if not healthy:
            print("[WARN] ChatGPT not ready. Is the page loaded in Chrome?")
            return

        # Test 1
        prompt = "What is 2+2? Answer in one sentence."
        print(f"\nSending: {prompt}")
        response = await connector.send(prompt, timeout_ms=30000)
        print(f"Response ({len(response)} chars):")
        print("-" * 40)
        print(response[:500])
        print("-" * 40)

        # Test 2
        prompt2 = "What is the capital of France?"
        print(f"\nSending: {prompt2}")
        response2 = await connector.send(prompt2, timeout_ms=30000)
        print(f"Response ({len(response2)} chars):")
        print("-" * 40)
        print(response2[:500])
        print("-" * 40)

        print("\n[OK] All tests passed")

    except Exception as e:
        print(f"\n[ERROR] {e}")

    finally:
        await connector.close()
        print("[OK] Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
