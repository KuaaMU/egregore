"""Synthesis models — the core of Egregore.

SynthesisResult is the most important entity in the system.

It represents what happens when multiple AI models reason about
the same question and their responses are analyzed for:
- Agreements (what they all see)
- Contradictions (where they diverge)
- Synthesis (a unified answer better than any individual)
- Uncertainty (what remains unknown)

This is NOT voting. This is NOT majority rule.
This is taking the best from each mind and creating
something none of them produced alone.

Why is this more important than Message?
- Message is a unit of communication (transport concern)
- SynthesisResult is a unit of intelligence (core value)

Egregore's core = SynthesisResult
LangGraph's core = State
Temporal's core = Workflow
Transformer's core = Attention
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class DifferenceType(str, Enum):
    """Types of differences between model responses.

    Not all differences are contradictions. Some are complementary.
    """

    CONTRADICTION = "contradiction"  # Models disagree (A vs B)
    EMPHASIS = "emphasis"  # Models focus on different aspects
    APPROACH = "approach"  # Models suggest different methods
    SCOPE = "scope"  # Models disagree on scope/extent
    UNCERTAINTY = "uncertainty"  # One model is uncertain, another is confident


class Difference(BaseModel):
    """A specific difference between model responses.

    Example:
        Difference(
            topic="Time Complexity",
            type=DifferenceType.CONTRADICTION,
            models={
                "gpt-4o": "O(n log n) with quicksort",
                "claude": "O(n) with radix sort",
            },
            analysis="Different algorithms suggested; depends on input constraints",
        )
    """

    model_config = {"frozen": True}

    topic: str
    type: DifferenceType
    models: dict[str, str] = Field(default_factory=dict)  # model_id → position
    analysis: str = ""


class SourceContribution(BaseModel):
    """What a specific model contributed to the synthesis.

    Enables: "This insight came from Claude, that from GPT."
    """

    model_config = {"frozen": True}

    model_id: str
    contributions: list[str] = Field(default_factory=list)
    strength: str = ""  # What this model was best at
    weight: float = 1.0  # How much influence in synthesis


class SynthesisResult(BaseModel):
    """The core entity of Egregore.

    This is what makes Egregore different from a chat aggregator.
    It represents the emergent intelligence of multiple models
    reasoning together.

    Fields:
        agreements: Points all models agree on
        contradictions: Points where models diverge
        unified_answer: The synthesized answer (better than any individual)
        confidence: Overall confidence (0.0 to 1.0)
        uncertainty: What remains unknown or disputed
        source_map: Which model contributed what
        metadata: Latency, models used, etc.
    """

    model_config = {"frozen": True}

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    prompt: str = ""

    # Core outputs
    agreements: list[str] = Field(default_factory=list)
    contradictions: list[Difference] = Field(default_factory=list)
    unified_answer: str = ""
    confidence: float = 0.0  # 0.0 to 1.0

    # What we don't know
    uncertainty: list[str] = Field(default_factory=list)

    # Attribution
    source_map: list[SourceContribution] = Field(default_factory=list)

    # Metadata
    models_used: list[str] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_agreements(self) -> bool:
        return len(self.agreements) > 0

    @property
    def has_contradictions(self) -> bool:
        return len(self.contradictions) > 0

    @property
    def agreement_count(self) -> int:
        return len(self.agreements)

    @property
    def contradiction_count(self) -> int:
        return len(self.contradictions)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.9:
            return "Very High"
        elif self.confidence >= 0.7:
            return "High"
        elif self.confidence >= 0.5:
            return "Moderate"
        elif self.confidence >= 0.3:
            return "Low"
        else:
            return "Very Low"

    def summary(self) -> str:
        """Human-readable summary for UI."""
        parts = []
        if self.agreements:
            parts.append(f"{len(self.agreements)} agreements")
        if self.contradictions:
            parts.append(f"{len(self.contradictions)} contradictions")
        parts.append(f"confidence: {self.confidence_label}")
        return " | ".join(parts)
