"""Application factory — creates and configures the FastAPI app.

Pattern: Application Factory / Composition Root

This is where all the pieces come together. The factory:
1. Creates the event bus
2. Creates the browser runtime (Playwright)
3. Creates the session manager
4. Creates and registers transports
5. Creates the health monitor & recovery manager
6. Creates the orchestrator
7. Initializes the router

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
from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.config.settings import settings
from egregore.domain.events.bus import EventBus
from egregore.domain.providers.base import ProviderConfig
from egregore.domain.providers.registry import ProviderRegistry
from egregore.infrastructure.browser.runtime.chromium import ChromiumRuntime
from egregore.infrastructure.browser.sessions.manager import SessionManager
from egregore.infrastructure.browser.health.monitor import HealthMonitor
from egregore.infrastructure.browser.recovery.manager import RecoveryManager
from egregore.infrastructure.providers.mock import MockProvider

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the Egregore application.

    This is the composition root — the only place that knows about
    all concrete implementations. Everything else uses abstractions.

    Dependency graph:
        EventBus
        ChromiumRuntime → SessionManager → BrowserTransport
        HealthMonitor → RecoveryManager
        ProviderRegistry → RoundTableOrchestrator
    """
    app = FastAPI(
        title="Egregore",
        description="Where Intelligence Emerges Together",
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

    # 1. Event Bus (the nervous system)
    event_bus = EventBus()

    # 2. Browser Runtime (Playwright engine)
    chromium = ChromiumRuntime(headless=settings.browser_headless)

    # 3. Session Manager (long-lived browser sessions)
    session_manager = SessionManager(runtime=chromium)

    # 4. Health Monitor
    health_monitor = HealthMonitor(event_bus=event_bus)

    # 5. Recovery Manager
    recovery_manager = RecoveryManager(
        session_manager=session_manager,
        runtime=chromium,
        event_bus=event_bus,
    )

    # 6. Provider Registry
    registry = ProviderRegistry()

    # 7. Register providers (browser transports or mock)
    _register_providers(registry, session_manager, health_monitor)

    # 8. Orchestrator
    orchestrator = RoundTableOrchestrator(
        registry=registry,
        event_bus=event_bus,
    )

    # 9. Initialize router
    init_chat_router(orchestrator, registry)

    # 10. Include router
    app.include_router(chat_router)

    # 11. Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "Egregore",
            "tagline": "Where Intelligence Emerges Together",
            "version": "0.2.0",
            "docs": "/docs",
        }

    # 12. Health endpoint
    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "providers": registry.provider_ids,
            "browser_running": chromium.is_running,
            "active_contexts": chromium.active_contexts,
            "health": {
                pid: {
                    "status": h.status.value,
                    "success_rate": h.success_rate,
                    "latency_ms": h.latency_ms,
                }
                for pid, h in health_monitor.get_all_health().items()
            },
        }

    # 13. Lifecycle events
    @app.on_event("startup")
    async def startup():
        await chromium.start()
        await health_monitor.start()
        logger.info("egregore_started", providers=registry.provider_ids)

    @app.on_event("shutdown")
    async def shutdown():
        await health_monitor.stop()
        await session_manager.close_all()
        await chromium.close()
        logger.info("egregore_stopped")

    logger.info(
        "app_created",
        providers=registry.provider_ids,
        debug=settings.debug,
    )

    return app


def _register_providers(
    registry: ProviderRegistry,
    session_manager: SessionManager,
    health_monitor: HealthMonitor,
) -> None:
    """Register all available providers.

    Strategy:
    1. If browser mode enabled → register browser transports
    2. If API keys available → register API providers
    3. Otherwise → register mock providers
    """
    has_providers = False

    # Browser transports (V0.5)
    if settings.browser_enabled:
        _register_browser_providers(registry, session_manager, health_monitor)
        has_providers = True

    # API providers (V1 — kept for when API is available)
    if settings.openai_api_key:
        _register_api_provider(
            registry, "openai", settings.openai_model, settings.openai_api_key
        )
        has_providers = True

    if settings.anthropic_api_key:
        _register_api_provider(
            registry, "anthropic", settings.anthropic_model, settings.anthropic_api_key
        )
        has_providers = True

    # Fallback: mock providers
    if not has_providers:
        logger.warning("no_providers_configured", action="registering_mocks")
        _register_mock_providers(registry)


def _register_browser_providers(
    registry: ProviderRegistry,
    session_manager: SessionManager,
    health_monitor: HealthMonitor,
) -> None:
    """Register browser-based transports."""
    from egregore.infrastructure.transport.chatgpt_browser import ChatGPTBrowserTransport

    # ChatGPT
    transport = ChatGPTBrowserTransport(session_manager=session_manager)
    # Wrap in a provider adapter
    from egregore.infrastructure.transport.provider_adapter import BrowserProviderAdapter

    provider = BrowserProviderAdapter(transport=transport, model="chatgpt-4")
    registry.register(provider)
    health_monitor.register("chatgpt", transport)
    logger.info("browser_provider_registered", provider="chatgpt")


def _register_api_provider(
    registry: ProviderRegistry, provider_id: str, model: str, api_key: str
) -> None:
    """Register an API-based provider."""
    if provider_id == "openai":
        from egregore.infrastructure.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(
            config=ProviderConfig(provider_id=provider_id, model=model, api_key=api_key)
        )
    elif provider_id == "anthropic":
        from egregore.infrastructure.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(
            config=ProviderConfig(provider_id=provider_id, model=model, api_key=api_key)
        )
    else:
        return

    registry.register(provider)
    logger.info("api_provider_registered", provider=provider_id, model=model)


def _register_mock_providers(registry: ProviderRegistry) -> None:
    """Register mock providers for development."""
    mock_configs = [
        ("mock-gpt4", "gpt-4o-sim", "Mock GPT-4o: I would analyze this step by step."),
        ("mock-claude", "claude-sim", "Mock Claude: Let me consider multiple perspectives."),
        ("mock-llama", "llama-sim", "Mock Llama: Here are several relevant points."),
    ]

    for provider_id, model, response in mock_configs:
        provider = MockProvider(
            config=ProviderConfig(provider_id=provider_id, model=model),
            response=response,
            latency_ms=150.0 + hash(provider_id) % 200,
        )
        registry.register(provider)
