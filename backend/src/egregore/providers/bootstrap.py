"""Browser Bootstrap — auto-detect and start Chrome with CDP.

Zero-config experience:
1. Check if CDP already running → use it
2. If Chrome running without CDP → restart it with CDP
3. If Chrome not running → start with CDP
4. Wait for CDP to be ready
5. Return

User never needs to know CDP exists.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger()

CDP_URL = "http://127.0.0.1:9222"
CDP_PORT = 9222

BROWSER_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


async def ensure_browser(headless: bool = False) -> str:
    """Ensure a browser with CDP is running. Returns CDP URL."""

    # Step 1: CDP already running?
    if await _is_cdp_running():
        logger.info("cdp_already_running")
        return CDP_URL

    # Step 2: Find browser
    browser_path = _find_browser()
    if not browser_path:
        raise RuntimeError(
            "No Chrome or Edge found. Install Chrome from google.com/chrome"
        )

    # Step 3: Chrome might be running without CDP — kill it first
    _kill_browser(browser_path)
    await asyncio.sleep(2)

    # Step 4: Start with CDP
    logger.info("starting_browser", path=str(browser_path))
    data_dir = Path.home() / ".egregore" / "chrome_debug"
    data_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(browser_path),
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={data_dir}",
    ]
    if headless:
        args.append("--headless=new")

    if sys.platform == "win32":
        subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 5: Wait for CDP
    for i in range(30):
        await asyncio.sleep(0.5)
        if await _is_cdp_running():
            logger.info("browser_ready", attempts=i + 1)
            return CDP_URL

    raise RuntimeError(
        f"Browser started but CDP not ready. Try manually:\n"
        f"  {browser_path} --remote-debugging-port={CDP_PORT}"
    )


async def _is_cdp_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{CDP_URL}/json/version")
            return resp.status_code == 200
    except Exception:
        return False


def _find_browser() -> Path | None:
    for path in BROWSER_PATHS:
        if path.exists():
            return path
    return None


def _kill_browser(browser_path: Path) -> None:
    """Kill existing browser process so we can restart with CDP."""
    exe_name = browser_path.name  # chrome.exe or msedge.exe
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/IM", exe_name],
                capture_output=True, timeout=5
            )
        else:
            subprocess.run(["pkill", "-f", exe_name], capture_output=True, timeout=5)
        logger.info("browser_killed", exe=exe_name)
    except Exception:
        pass  # Browser might not be running
