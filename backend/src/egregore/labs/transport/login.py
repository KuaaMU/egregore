"""Chrome CDP Setup Helper — tells user how to start Chrome with debugging.

Usage:
    uv run python -m egregore.labs.transport.login

This prints instructions for starting Chrome with --remote-debugging-port.
After that, Egregore connects via CDP. No manual login needed.
"""

import asyncio
import sys

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTConnector


async def main():
    print("=" * 60)
    print("Egregore Chrome Connector Setup")
    print("=" * 60)
    print()
    print("Step 1: Close ALL Chrome windows.")
    print()
    print("Step 2: Start Chrome with remote debugging:")
    print()
    print('  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
    print()
    print("Step 3: Login to ChatGPT in that Chrome window.")
    print()
    print("Step 4: Run this command to verify connection:")
    print()
    print("  uv run python -m egregore.labs.transport.login --verify")
    print()
    print("=" * 60)

    if "--verify" in sys.argv:
        print("\nVerifying connection...")
        connector = ChatGPTConnector()
        try:
            await connector.connect()
            healthy = await connector.health_check()
            if healthy:
                print("[OK] Connected to Chrome. ChatGPT is ready.")
            else:
                print("[WARN] Connected but ChatGPT not ready. Is the page loaded?")
            await connector.close()
        except Exception as e:
            print(f"[ERROR] {e}")
            print("\nMake sure Chrome is running with --remote-debugging-port=9222")


if __name__ == "__main__":
    asyncio.run(main())
