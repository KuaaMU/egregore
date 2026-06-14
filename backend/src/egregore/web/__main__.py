"""Run Egregore Web UI.

Usage:
    uv run python -m egregore.web
"""

import uvicorn
from egregore.web.app import create_web_app

app = create_web_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
