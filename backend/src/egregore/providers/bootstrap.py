"""Browser Bootstrap — login helper.

Usage:
    uv run python -m egregore.login

Opens visible Chrome. User logs into platforms.
Profile saved to ~/.egregore/profile/.
After this, all runs are headless and silent.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from egregore.providers.browser_manager import BrowserManager

DEFAULT_PROFILE_DIR = Path.home() / ".egregore" / "profile"


async def login_interactive() -> None:
    """Open visible Chrome for manual login.

    User logs into ChatGPT, Grok, Kimi, Qwen, Doubao.
    Profile is saved. Subsequent runs use headless mode.
    """
    print("=" * 50)
    print("Egregore — Login")
    print("=" * 50)
    print()
    print(f"Profile directory: {DEFAULT_PROFILE_DIR}")
    print()
    print("A browser window will open.")
    print("Please log into your AI platforms:")
    print("  - ChatGPT: https://chatgpt.com/")
    print("  - Grok: https://grok.com/")
    print("  - Kimi: https://kimi.moonshot.cn/")
    print("  - Qwen: https://tongyi.aliyun.com/qianwen/")
    print("  - Doubao: https://www.doubao.com/")
    print()
    print("After logging in, press Enter here to save and close.")
    print()

    # Open visible browser
    manager = BrowserManager(headless=False)
    await manager.connect()

    # Open tabs for each platform
    platforms = [
        ("ChatGPT", "https://chatgpt.com/"),
        ("Grok", "https://grok.com/"),
        ("Kimi", "https://kimi.moonshot.cn/"),
        ("Qwen", "https://tongyi.aliyun.com/qianwen/"),
        ("Doubao", "https://www.doubao.com/"),
    ]

    for name, url in platforms:
        try:
            await manager.get_page(url)
            print(f"  Opened {name}")
        except Exception as e:
            print(f"  Failed to open {name}: {e}")

    print()
    input("Press Enter after logging in to all platforms...")

    # Close browser (profile is saved automatically)
    await manager.close()
    print()
    print(f"Profile saved to: {DEFAULT_PROFILE_DIR}")
    print("From now on, Egregore runs headless with your login state.")
    print()


if __name__ == "__main__":
    asyncio.run(login_interactive())
