"""Entry point for running Egregore with `python -m egregore`."""

import uvicorn

from egregore.config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "egregore.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
