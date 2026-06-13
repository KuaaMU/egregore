"""API schemas — request/response models for the REST API.

Pattern: DTO (Data Transfer Object)

These schemas are the contract between frontend and backend.
They are separate from domain entities because:
1. API schema evolution is independent of domain evolution
2. We can add API-specific fields (e.g., request_id)
3. We can hide internal fields from the API

Why Pydantic? FastAPI uses it for validation and docs generation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request to start a round-table discussion."""

    prompt: str = Field(..., min_length=1, max_length=10000, description="The user's question")
    system_prompt: str = Field(
        default="",
        max_length=5000,
        description="Optional system prompt for all providers",
    )
    provider_ids: list[str] | None = Field(
        default=None,
        description="Specific providers to use (None = all)",
    )


class ProviderResponseSchema(BaseModel):
    """A single provider's response."""

    provider_id: str
    model: str
    content: str
    latency_ms: float
    token_count: int
    error: str | None = None


class ConsensusSchema(BaseModel):
    """The synthesized consensus (V1: simple summary)."""

    common_points: list[str]
    differences: list[str]
    synthesis: str
    confidence: float = Field(ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """Response from the round-table discussion."""

    id: str
    prompt: str
    responses: list[ProviderResponseSchema]
    consensus: ConsensusSchema | None = None
    total_latency_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    providers: list[str]
    version: str = "0.1.0"
