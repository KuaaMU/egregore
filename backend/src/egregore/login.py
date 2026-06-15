"""Login — one-time visible browser for manual login.

Flow:
1. Open visible Chrome (Playwright managed)
2. User logs into platforms manually
3. Cookies saved to ~/.egregore/profile/ (Playwright format)
4. Close browser
5. All subsequent runs: headless with saved cookies (silent)

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
    print("Egregore — First Time Login")
    print("=" * 50)
    print()
    print("A browser window will open.")
    print("Log into each platform you want to use.")
    print("When done, press Enter here to save and close.")
    print()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Launch visible browser with persistent profile
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
        )

        # Open tabs for each platform
        for name, url in PLATFORMS:
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                print(f"  Opened {name}: {url}")
            except Exception as e:
                print(f"  Failed {name}: {e}")

        print()
        input("Press Enter after logging in to all platforms...")

        # Close (cookies saved automatically by Playwright)
        await context.close()

    print()
    print(f"Session saved to: {PROFILE_DIR}")
    print("Egregore will now run silently with your login state.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
