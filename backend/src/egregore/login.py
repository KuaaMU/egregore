"""Login — one-time visible browser for manual login.

After login, Playwright saves cookies to ~/.egregore/profile/
in its own format (not Chrome's encrypted format).

All subsequent runs use headless mode with the saved profile.
Completely silent. No browser popup.

Usage:
    uv run python -m egregore.login
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

PROFILE_DIR = Path.home() / ".egregore" / "profile"

PLATFORMS = [
    ("ChatGPT", "https://chatgpt.com/"),
    ("Grok", "https://grok.com/"),
    ("Kimi", "https://kimi.moonshot.cn/"),
    ("Qwen", "https://tongyi.aliyun.com/qianwen/"),
    ("Doubao", "https://www.doubao.com/"),
]


async def main():
    print("=" * 50)
    print("Egregore — One-Time Login")
    print("=" * 50)
    print()
    print("A browser will open. Log into the platforms you use.")
    print("This only needs to be done once.")
    print("After this, Egregore runs silently in the background.")
    print()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        # Open tabs
        for name, url in PLATFORMS:
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                print(f"  Opened {name}")
            except Exception as e:
                print(f"  Failed {name}: {e}")

        print()
        input("Press Enter after logging in to all platforms...")

        # Playwright automatically saves cookies/localStorage to PROFILE_DIR
        await context.close()

    print()
    print(f"Session saved to: {PROFILE_DIR}")
    print("From now on: uv run python -m egregore.web  (silent, no popup)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
