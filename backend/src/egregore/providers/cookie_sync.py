"""Cookie Sync — copy cookies from user's Chrome to Egregore profile.

One-time operation. Chrome must be closed.
After sync, Egregore runs headless with the user's login state.

Usage:
    uv run python -m egregore.sync
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger()

# Chrome profile locations on Windows
CHROME_PROFILES = [
    Path.home() / "AppData/Local/Google/Chrome/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
]

EGREGORE_PROFILE = Path.home() / ".egregore" / "profile"


def find_chrome_profile() -> Path | None:
    """Find the user's Chrome profile directory."""
    for profile in CHROME_PROFILES:
        if profile.exists():
            return profile
    return None


def sync_cookies(chrome_profile: Path, egregore_profile: Path) -> int:
    """Copy cookies from Chrome to Egregore profile.

    Args:
        chrome_profile: Path to Chrome User Data directory
        egregore_profile: Path to Egregore profile directory

    Returns:
        Number of cookies copied
    """
    egregore_profile.mkdir(parents=True, exist_ok=True)

    # Find the Default profile
    default_profile = chrome_profile / "Default"
    if not default_profile.exists():
        # Try Profile 1, Profile 2, etc.
        for p in chrome_profile.iterdir():
            if p.is_dir() and p.name.startswith("Profile"):
                default_profile = p
                break

    if not default_profile.exists():
        logger.error("chrome_profile_not_found", path=str(chrome_profile))
        return 0

    # Copy cookies database
    cookies_src = default_profile / "Cookies"
    if not cookies_src.exists():
        logger.error("cookies_not_found", path=str(cookies_src))
        return 0

    # Create Egregore Default profile
    egregore_default = egregore_profile / "Default"
    egregore_default.mkdir(parents=True, exist_ok=True)

    # Copy cookies
    cookies_dst = egregore_default / "Cookies"
    shutil.copy2(cookies_src, cookies_dst)

    # Copy Local State (needed for cookie decryption)
    local_state_src = chrome_profile / "Local State"
    if local_state_src.exists():
        shutil.copy2(local_state_src, egregore_profile / "Local State")

    # Copy other important files
    for filename in ["Login Data", "Web Data", "Preferences", "Secure Preferences"]:
        src = default_profile / filename
        if src.exists():
            shutil.copy2(src, egregore_default / filename)

    # Count cookies
    try:
        conn = sqlite3.connect(str(cookies_dst))
        count = conn.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
        conn.close()
    except Exception:
        count = -1

    logger.info("cookies_synced", count=count, profile=str(egregore_profile))
    return count


def sync_local_storage(chrome_profile: Path, egregore_profile: Path) -> int:
    """Copy localStorage from Chrome to Egregore profile."""
    default_profile = chrome_profile / "Default"
    if not default_profile.exists():
        return 0

    egregore_default = egregore_profile / "Default"
    egregore_default.mkdir(parents=True, exist_ok=True)

    # Copy Local Storage
    ls_src = default_profile / "Local Storage"
    if ls_src.exists():
        ls_dst = egregore_default / "Local Storage"
        if ls_dst.exists():
            shutil.rmtree(ls_dst)
        shutil.copytree(ls_src, ls_dst)
        logger.info("local_storage_synced")
        return 1
    return 0


def run_sync() -> None:
    """Run the full cookie sync process."""
    print("=" * 50)
    print("Egregore — Cookie Sync")
    print("=" * 50)
    print()

    # Check Chrome is closed
    chrome_profile = find_chrome_profile()
    if not chrome_profile:
        print("Error: Chrome profile not found.")
        print("Expected: ~/AppData/Local/Google/Chrome/User Data")
        return

    print(f"Chrome profile: {chrome_profile}")
    print(f"Egregore profile: {EGREGORE_PROFILE}")
    print()

    # Check if Chrome is running
    try:
        import subprocess
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
            capture_output=True, text=True, timeout=5
        )
        if "chrome.exe" in result.stdout:
            print("WARNING: Chrome is running. Please close Chrome first.")
            print("  Cookies may not be fully copied while Chrome is open.")
            print()
            resp = input("Continue anyway? (y/N): ")
            if resp.lower() != 'y':
                return
    except Exception:
        pass

    print("Syncing cookies...")
    cookie_count = sync_cookies(chrome_profile, EGREGORE_PROFILE)
    print(f"  Cookies: {cookie_count}")

    print("Syncing localStorage...")
    sync_local_storage(chrome_profile, EGREGORE_PROFILE)
    print(f"  LocalStorage: done")

    print()
    print(f"Profile saved to: {EGREGORE_PROFILE}")
    print("Egregore will now run headless with your login state.")
    print()


if __name__ == "__main__":
    run_sync()
