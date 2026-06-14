"""Test ChatGPT provider.

Usage:
    1. Start Chrome: chrome.exe --remote-debugging-port=9222 --user-data-dir=...
    2. Login to ChatGPT
    3. Run: uv run python -m egregore.labs.transport.test_chatgpt
"""

import asyncio

from egregore.providers.chatgpt.connector import ChatGPTProvider


async def main():
    print("Connecting to ChatGPT...")
    provider = ChatGPTProvider()

    try:
        await provider.connect()
        print(f"[OK] Connected. Status: {provider.status.value}")
        print(f"[OK] Capabilities: {provider.capabilities.models}")

        # Test 1
        response = await provider.send("What is 2+2? Answer in one sentence.")
        print(f"\n[OK] Response ({response.latency_ms:.0f}ms):")
        print(f"  {response.content[:200]}")

        # Test 2
        response2 = await provider.send("Name three programming languages.")
        print(f"\n[OK] Response ({response2.latency_ms:.0f}ms):")
        print(f"  {response2.content[:200]}")

        print(f"\n[OK] All tests passed")

    except Exception as e:
        print(f"\n[ERROR] {e}")

    finally:
        await provider.close()
        print("[OK] Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
