"""Login entry point.

Usage:
    uv run python -m egregore.sync   # Copy cookies from Chrome (one-time)
    uv run python -m egregore.login  # Open browser for manual login (fallback)
"""

import asyncio
import sys

from egregore.providers.bootstrap import login_interactive
from egregore.providers.cookie_sync import run_sync


def main():
    if "--sync" in sys.argv or len(sys.argv) == 1:
        run_sync()
    else:
        asyncio.run(login_interactive())


if __name__ == "__main__":
    main()
