"""Cookie Sync entry point.

Usage:
    uv run python -m egregore.sync
"""

from egregore.providers.cookie_sync import run_sync

if __name__ == "__main__":
    run_sync()
