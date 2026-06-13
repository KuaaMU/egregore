"""Application factory — creates and configures the FastAPI app.

Pattern: Application Factory / Composition Root

This is where all the pieces come together.

V1 flow:
    User Prompt → Round Table (parallel dispatch) → Synthesis Engine → Result
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from egregore.api.routers.chat import init_chat_router, router as chat_router
from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.application.synthesis.engine import SynthesisEngine
from egregore.config.settings import settings
from egregore.domain.events.bus import EventBus
from egregore.domain.providers.base import ProviderConfig
from egregore.domain.providers.registry import ProviderRegistry
from egregore.infrastructure.providers.mock import MockProvider

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the Egregore application.

    Dependency graph:
        EventBus
        ProviderRegistry → RoundTableOrchestrator
        SynthesisEngine (uses a provider as synthesizer)
        → ChatRouter
    """
    app = FastAPI(
        title="Egregore",
        description="A Synthesis Engine for Collective Intelligence",
        version="0.2.0",
    )

    # CORS
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

    # 5. Synthesis Engine
    synthesis = _create_synthesis_engine(registry)

    # 6. Initialize router
    init_chat_router(orchestrator, registry, synthesis)

    # 7. Include router
    app.include_router(chat_router)

    # 8. Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "Egregore",
            "tagline": "A Synthesis Engine for Collective Intelligence",
            "version": "0.2.0",
            "docs": "/docs",
        }

    # 9. Health endpoint
    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "providers": registry.provider_ids,
            "synthesis_enabled": synthesis is not None,
        }

    logger.info(
        "app_created",
        providers=registry.provider_ids,
        synthesis_enabled=synthesis is not None,
    )

    return app


def _register_providers(registry: ProviderRegistry) -> None:
    """Register available providers.

    Priority:
    1. API keys → register real providers
    2. No keys → register mock providers
    """
    has_providers = False

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
        has_providers = True
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
        has_providers = True
        logger.info("provider_registered", provider="anthropic", model=settings.anthropic_model)

    # Fallback: mock providers
    if not has_providers:
        logger.warning("no_api_keys_found", action="registering_mock_providers")
        _register_mock_providers(registry)


def _register_mock_providers(registry: ProviderRegistry) -> None:
    """Register mock providers for development."""
    mock_configs = [
        (
            "mock-gpt4",
            "gpt-4o-sim",
            "From an engineering perspective, I'd recommend Rust for this use case. "
            "The memory safety guarantees without garbage collection make it ideal for "
            "systems programming. The learning curve is steep but the long-term benefits "
            "are significant. Consider using Tokio for async runtime.",
        ),
        (
            "mock-claude",
            "claude-sim",
            "I'd approach this differently. While Rust has clear performance advantages, "
            "Go offers a better balance of simplicity and performance for most teams. "
            "The goroutine model is elegant for concurrent workloads, and the ecosystem "
            "is mature. Unless you need zero-cost abstractions, Go is the pragmatic choice.",
        ),
        (
            "mock-llama",
            "llama-sim",
            "Both Rust and Go are excellent choices. For your specific requirements, "
            "I'd suggest starting with Go for the rapid prototyping phase, then evaluating "
            "whether performance-critical components need Rust. A hybrid approach often "
            "works best in practice. Consider the team's existing expertise.",
        ),
    ]

    for provider_id, model, response in mock_configs:
        provider = MockProvider(
            config=ProviderConfig(provider_id=provider_id, model=model),
            response=response,
            latency_ms=150.0 + hash(provider_id) % 200,
        )
        registry.register(provider)


def _create_synthesis_engine(registry: ProviderRegistry) -> SynthesisEngine | None:
    """Create the synthesis engine.

    The synthesizer is a fast, cheap model that analyzes other models' responses.
    Priority: OpenAI (fast model) → Anthropic → first available provider → mock
    """
    # Try to use a fast model for synthesis
    if settings.openai_api_key:
        from egregore.infrastructure.providers.openai_provider import OpenAIProvider

        synthesizer = OpenAIProvider(
            config=ProviderConfig(
                provider_id="synthesizer",
                model="gpt-4o-mini",  # Fast and cheap
                api_key=settings.openai_api_key,
            )
        )
        logger.info("synthesis_engine_created", model="gpt-4o-mini")
        return SynthesisEngine(synthesizer=synthesizer)

    if settings.anthropic_api_key:
        from egregore.infrastructure.providers.anthropic_provider import AnthropicProvider

        synthesizer = AnthropicProvider(
            config=ProviderConfig(
                provider_id="synthesizer",
                model="claude-haiku-4-5-20251001",  # Fast and cheap
                api_key=settings.anthropic_api_key,
            )
        )
        logger.info("synthesis_engine_created", model="claude-haiku-4-5-20251001")
        return SynthesisEngine(synthesizer=synthesizer)

    # No real providers — use mock for development
    logger.warning("no_synthesizer_available", action="using_mock")
    mock_synth = MockProvider(
        config=ProviderConfig(provider_id="synthesizer", model="mock-synth"),
        response='{"unified_answer": "Mock synthesis: All models provide valuable perspectives. Consider a hybrid approach.", "confidence": 0.75, "uncertainty": ["Team expertise not considered"], "contributions": [{"model_id": "mock-gpt4", "contributions": ["Performance analysis"], "strength": "Engineering rigor"}, {"model_id": "mock-claude", "contributions": ["Pragmatic tradeoffs"], "strength": "Practical considerations"}, {"model_id": "mock-llama", "contributions": ["Hybrid approach"], "strength": "Balanced perspective"}]}',
        latency_ms=100.0,
    )
    return SynthesisEngine(synthesizer=mock_synth)
