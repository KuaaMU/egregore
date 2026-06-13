"""Login helper — one-time manual login to ChatGPT.

Run this ONCE to login manually. After login, the session is saved
to persistent context. All subsequent runs use headless mode.

Usage:
    uv run python -m egregore.labs.transport.login

This will:
1. Open Chromium (visible) with persistent context
2. Navigate to ChatGPT
3. Wait for you to login manually
4. Save the session
5. Close

After this, run reliability test with headless=True (default).
"""

import asyncio
import sys

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTAdapter


async def main():
    print("Opening ChatGPT for manual login...")
    print("Please login to ChatGPT in the browser window.")
    print("After login, press Enter here to save and close.")
    print()

    # Open non-headless for manual login
    adapter = ChatGPTAdapter(headless=False)
    await adapter.launch()

    print("[OK] Browser opened. Please login to ChatGPT.")
    print()

    # Wait for user to finish login
    input("Press Enter after you have logged in...")

    # Verify login worked
    healthy = await adapter.health_check()
    if healthy:
        print("[OK] Login successful! Session saved.")
    else:
        print("[WARN] Could not verify login. Please try again.")

    await adapter.close()
    print("[OK] Done. You can now run the reliability test with headless mode.")


if __name__ == "__main__":
    asyncio.run(main())
