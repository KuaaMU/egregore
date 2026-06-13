"""Chat router — REST endpoints for the round-table flow.

Pattern: Controller / Route Handler

This router is thin — it validates input, delegates to the orchestrator
and synthesis engine, and formats the output.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from egregore.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    DifferenceSchema,
    HealthResponse,
    ProviderResponseSchema,
    SourceContributionSchema,
    SynthesisSchema,
)
from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.application.synthesis.engine import SynthesisEngine
from egregore.domain.providers.registry import ProviderRegistry

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Dependency injection via closure
_orchestrator: RoundTableOrchestrator | None = None
_synthesis: SynthesisEngine | None = None
_registry: ProviderRegistry | None = None


def init_chat_router(
    orchestrator: RoundTableOrchestrator,
    registry: ProviderRegistry,
    synthesis: SynthesisEngine | None = None,
) -> None:
    """Initialize the chat router with dependencies."""
    global _orchestrator, _registry, _synthesis
    _orchestrator = orchestrator
    _registry = registry
    _synthesis = synthesis


@router.post("/round-table", response_model=ChatResponse)
async def round_table(request: ChatRequest) -> ChatResponse:
    """Execute a round-table discussion with synthesis.

    Flow:
    1. Dispatch prompt to all providers in parallel
    2. Collect responses
    3. Synthesize agreements, contradictions, unified answer
    4. Return everything
    """
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    # Step 1+2: Round table (parallel dispatch + collect)
    result = await _orchestrator.execute(
        prompt=request.prompt,
        system_prompt=request.system_prompt,
    )

    # Map provider responses
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

    # Step 3: Synthesis
    synthesis_schema = None
    if _synthesis is not None:
        # Collect successful responses as Messages
        messages = [r.message for r in result.results if r.success and r.message]
        if len(messages) >= 2:  # Need at least 2 responses to synthesize
            try:
                synthesis_result = await _synthesis.synthesize(
                    prompt=request.prompt,
                    responses=messages,
                )
                synthesis_schema = SynthesisSchema(
                    agreements=synthesis_result.agreements,
                    contradictions=[
                        DifferenceSchema(
                            topic=c.topic,
                            type=c.type.value,
                            models=c.models,
                            analysis=c.analysis,
                        )
                        for c in synthesis_result.contradictions
                    ],
                    unified_answer=synthesis_result.unified_answer,
                    confidence=synthesis_result.confidence,
                    uncertainty=synthesis_result.uncertainty,
                    source_map=[
                        SourceContributionSchema(
                            model_id=s.model_id,
                            contributions=s.contributions,
                            strength=s.strength,
                        )
                        for s in synthesis_result.source_map
                    ],
                )
            except Exception as e:
                import structlog

                logger = structlog.get_logger()
                logger.error("synthesis_failed", error=str(e))

    return ChatResponse(
        id=f"rt_{result.prompt[:8]}",
        prompt=result.prompt,
        responses=responses,
        synthesis=synthesis_schema,
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
