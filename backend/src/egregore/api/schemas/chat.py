"""API schemas — request/response models for the REST API.

Pattern: DTO (Data Transfer Object)

These schemas are the contract between frontend and backend.
They map domain entities to API responses.
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


class DifferenceSchema(BaseModel):
    """A difference between model responses."""

    topic: str
    type: str  # contradiction, emphasis, approach, scope, uncertainty
    models: dict[str, str] = Field(default_factory=dict)
    analysis: str = ""


class SourceContributionSchema(BaseModel):
    """What a model contributed to the synthesis."""

    model_id: str
    contributions: list[str] = Field(default_factory=list)
    strength: str = ""


class SynthesisSchema(BaseModel):
    """The synthesized result — the core output of Egregore.

    This is what makes Egregore different from a chat aggregator.
    """

    agreements: list[str] = Field(default_factory=list)
    contradictions: list[DifferenceSchema] = Field(default_factory=list)
    unified_answer: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    uncertainty: list[str] = Field(default_factory=list)
    source_map: list[SourceContributionSchema] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Response from the round-table discussion."""

    id: str
    prompt: str
    responses: list[ProviderResponseSchema]
    synthesis: SynthesisSchema | None = None
    total_latency_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    providers: list[str]
    version: str = "0.1.0"
