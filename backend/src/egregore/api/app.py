"""Application factory — creates and configures the FastAPI app.

Pattern: Application Factory / Composition Root

This is where all the pieces come together. The factory:
1. Creates the event bus
2. Creates and registers providers
3. Creates the orchestrator
4. Initializes the router
5. Configures middleware

Why a factory function over a global app?
- Testable — we can create multiple instances with different configs
- Explicit dependency wiring
- No import-time side effects
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from egregore.api.routers.chat import init_chat_router, router as chat_router
from egregore.api.schemas.chat import HealthResponse
from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.config.settings import settings
from egregore.domain.events.bus import EventBus
from egregore.domain.providers.base import ProviderConfig
from egregore.domain.providers.registry import ProviderRegistry
from egregore.infrastructure.providers.mock import MockProvider

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the Egregore application.

    This is the composition root — the only place that knows about
    all concrete implementations. Everything else uses abstractions.
    """
    app = FastAPI(
        title="Egregore",
        description="Where Intelligence Emerges Together",
        version="0.1.0",
    )

    # CORS — allow frontend to talk to backend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # === Wire up dependencies ===

    # 1. Event Bus
    event_bus = EventBus()

    # 2. Provider Registry
    registry = ProviderRegistry()

    # 3. Register providers
    _register_providers(registry)

    # 4. Orchestrator
    orchestrator = RoundTableOrchestrator(
        registry=registry,
        event_bus=event_bus,
    )

    # 5. Initialize router
    init_chat_router(orchestrator, registry)

    # 6. Include router
    app.include_router(chat_router)

    # 7. Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "Egregore",
            "tagline": "Where Intelligence Emerges Together",
            "version": "0.1.0",
            "docs": "/docs",
        }

    logger.info(
        "app_created",
        providers=registry.provider_ids,
        debug=settings.debug,
    )

    return app


def _register_providers(registry: ProviderRegistry) -> None:
    """Register all available providers.

    This function checks which API keys are configured and
    registers the corresponding providers. If no keys are set,
    it falls back to mock providers for development.

    Pattern: Factory Method — creates providers based on config.
    """
    has_real_providers = False

    # OpenAI
    if settings.openai_api_key:
        from egregore.infrastructure.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(
            config=ProviderConfig(
                provider_id="openai",
                model=settings.openai_model,
                api_key=settings.openai_api_key,
            )
        )
        registry.register(provider)
        has_real_providers = True
        logger.info("provider_registered", provider="openai", model=settings.openai_model)

    # Anthropic
    if settings.anthropic_api_key:
        from egregore.infrastructure.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(
            config=ProviderConfig(
                provider_id="anthropic",
                model=settings.anthropic_model,
                api_key=settings.anthropic_api_key,
            )
        )
        registry.register(provider)
        has_real_providers = True
        logger.info("provider_registered", provider="anthropic", model=settings.anthropic_model)

    # Fallback: mock providers for development
    if not has_real_providers:
        logger.warning("no_api_keys_found", action="registering_mock_providers")

        mock_configs = [
            ("mock-gpt4", "gpt-4o-sim", "Mock GPT-4o: I would approach this by analyzing the problem step by step."),
            ("mock-claude", "claude-sim", "Mock Claude: Let me think about this carefully. The key insight here is that we should consider multiple perspectives."),
            ("mock-llama", "llama-sim", "Mock Llama: Based on my training data, I can provide several relevant points on this topic."),
        ]

        for provider_id, model, response in mock_configs:
            provider = MockProvider(
                config=ProviderConfig(provider_id=provider_id, model=model),
                response=response,
                latency_ms=150.0 + hash(provider_id) % 200,
            )
            registry.register(provider)
