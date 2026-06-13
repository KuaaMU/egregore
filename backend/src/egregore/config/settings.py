"""Application settings — centralized configuration.

Pattern: Configuration Object

All settings live here, loaded from environment variables.
This prevents scattered env var reads and makes configuration testable.

Why pydantic-settings over plain dict?
- Type validation
- Default values
- Environment variable binding
- .env file support
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Egregore application settings.

    All configuration is loaded from environment variables.
    Prefix: EGREGORE_ (e.g., EGREGORE_DEBUG=true)
    """

    # App
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Provider API Keys (optional — not all providers need to be active)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # Default models
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    openrouter_model: str = "meta-llama/llama-3.1-70b-instruct"

    # Summary engine (V1: local Ollama)
    summary_model: str = "qwen3:4b"
    summary_endpoint: str = "http://localhost:11434"

    model_config = {"env_prefix": "EGREGORE_", "env_file": ".env"}


settings = Settings()
