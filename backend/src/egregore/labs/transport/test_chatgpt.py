"""Test ChatGPT Browser Adapter — manual verification.

Run this to verify the adapter works with real ChatGPT.

Usage:
    uv run python -m egregore.labs.transport.test_chatgpt

This will:
1. Launch Chromium with persistent context
2. Navigate to ChatGPT
3. Send a test prompt
4. Print the response
5. Check health
6. Close

First run will need manual login (non-headless).
Subsequent runs reuse the saved session.
"""

import asyncio
import sys

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTAdapter


async def main():
    headless = "--headless" in sys.argv

    print(f"Launching ChatGPT adapter (headless={headless})...")
    adapter = ChatGPTAdapter(headless=headless)

    try:
        await adapter.launch()
        print("✓ Launched")

        # Health check
        healthy = await adapter.health_check()
        print(f"✓ Health: {'OK' if healthy else 'FAILED'}")

        if not healthy:
            print("⚠ ChatGPT not ready. You may need to login manually.")
            print("  Run without --headless to login interactively.")
            return

        # Send test prompt
        prompt = "What is 2+2? Answer in one sentence."
        print(f"\nSending: {prompt}")
        print("Waiting for response...")

        response = await adapter.send(prompt, timeout_ms=30000)
        print(f"\nResponse ({len(response)} chars):")
        print("-" * 40)
        print(response)
        print("-" * 40)

        # Second test
        prompt2 = "What is the capital of France?"
        print(f"\nSending: {prompt2}")
        response2 = await adapter.send(prompt2, timeout_ms=30000)
        print(f"\nResponse ({len(response2)} chars):")
        print("-" * 40)
        print(response2)
        print("-" * 40)

        print("\n✓ All tests passed")

    except Exception as e:
        print(f"\n✗ Error: {e}")

    finally:
        await adapter.close()
        print("✓ Closed")


if __name__ == "__main__":
    asyncio.run(main())
