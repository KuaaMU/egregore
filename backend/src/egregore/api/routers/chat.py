"""Chat router — REST endpoints for the round-table flow.

Pattern: Controller / Route Handler

This router is thin — it validates input, delegates to the orchestrator,
and formats the output. Business logic lives in the orchestrator.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from egregore.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ProviderResponseSchema,
)
from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.domain.providers.registry import ProviderRegistry

router = APIRouter(prefix="/api/chat", tags=["chat"])

# These are set by the app factory — dependency injection via closure
_orchestrator: RoundTableOrchestrator | None = None
_registry: ProviderRegistry | None = None


def init_chat_router(orchestrator: RoundTableOrchestrator, registry: ProviderRegistry) -> None:
    """Initialize the chat router with dependencies.

    Called once at startup. This is a simple form of dependency injection.
    FastAPI's Depends() is another option, but this is clearer for our case.
    """
    global _orchestrator, _registry
    _orchestrator = orchestrator
    _registry = registry


@router.post("/round-table", response_model=ChatResponse)
async def round_table(request: ChatRequest) -> ChatResponse:
    """Execute a round-table discussion.

    This is the main endpoint. It:
    1. Validates the request
    2. Delegates to the orchestrator
    3. Maps domain results to API schemas
    """
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    result = await _orchestrator.execute(
        prompt=request.prompt,
        system_prompt=request.system_prompt,
    )

    # Map domain results to API schema
    responses = []
    for r in result.results:
        responses.append(
            ProviderResponseSchema(
                provider_id=r.provider_id,
                model=r.model,
                content=r.message.content if r.message else "",
                latency_ms=r.latency_ms,
                token_count=(
                    r.message.provider_meta.token_count
                    if r.message and r.message.provider_meta
                    else 0
                ),
                error=r.error,
            )
        )

    return ChatResponse(
        id=f"rt_{result.prompt[:8]}",
        prompt=result.prompt,
        responses=responses,
        total_latency_ms=result.total_latency_ms,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health and available providers."""
    if _registry is None:
        return HealthResponse(status="initializing", providers=[])

    return HealthResponse(
        status="ok",
        providers=_registry.provider_ids,
    )
