"""Browser Bootstrap — auto-detect and start Chrome with CDP.

Zero-config experience:
1. Check if CDP already running → use it
2. Find Chrome/Edge installation
3. Start with --remote-debugging-port=9222
4. Wait for CDP to be ready
5. Return

User never needs to know CDP exists.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

import structlog
import httpx

logger = structlog.get_logger()

CDP_URL = "http://127.0.0.1:9222"
CDP_PORT = 9222

# Chrome/Edge installation paths on Windows
BROWSER_PATHS = [
    # Chrome
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    # Edge
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


async def ensure_browser(data_dir: Path | None = None, headless: bool = False) -> str:
    """Ensure a browser with CDP is running. Returns CDP URL.

    Steps:
    1. Check if CDP already running
    2. If not, find and start Chrome/Edge
    3. Wait for CDP to be ready
    4. Return CDP URL

    Raises RuntimeError if no browser found.
    """
    # Step 1: Check if CDP already running
    if await _is_cdp_running():
        logger.info("cdp_already_running", url=CDP_URL)
        return CDP_URL

    # Step 2: Find browser
    browser_path = _find_browser()
    if not browser_path:
        raise RuntimeError(
            "No Chrome or Edge found. Install Chrome or Edge, or start manually:\n"
            "  chrome.exe --remote-debugging-port=9222"
        )

    # Step 3: Start browser
    logger.info("starting_browser", path=str(browser_path))
    args = [str(browser_path), f"--remote-debugging-port={CDP_PORT}"]

    if data_dir:
        data_dir.mkdir(parents=True, exist_ok=True)
        args.append(f"--user-data-dir={data_dir}")

    if headless:
        args.append("--headless=new")

    # Anti-detection
    args.append("--disable-blink-features=AutomationControlled")

    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 4: Wait for CDP to be ready
    for i in range(30):  # 15 seconds max
        await asyncio.sleep(0.5)
        if await _is_cdp_running():
            logger.info("browser_started", url=CDP_URL, attempts=i + 1)
            return CDP_URL

    raise RuntimeError(
        f"Browser started but CDP not ready at {CDP_URL}. "
        f"Try manually: {browser_path} --remote-debugging-port={CDP_PORT}"
    )


async def _is_cdp_running() -> bool:
    """Check if CDP is accessible."""
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{CDP_URL}/json/version")
            return resp.status_code == 200
    except Exception:
        return False


def _find_browser() -> Path | None:
    """Find the first available browser installation."""
    for path in BROWSER_PATHS:
        if path.exists():
            return path
    return None
