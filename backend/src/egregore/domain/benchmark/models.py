"""Benchmark models — evaluation infrastructure for Egregore.

BenchmarkCase is the unit of evaluation. It captures:
- The question
- Individual model responses + scores
- Synthesis result + score
- Whether synthesis beat the best individual

This is how we prove that collective intelligence works.

Why is this important?
- Without data, "synthesis is better" is just a hypothesis
- BenchmarkCase turns it into a measurable claim
- We need Synthesis Win Rate > 70% to justify Egregore's existence
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class Domain(str, Enum):
    """Question domains for benchmarking."""

    SOFTWARE = "software"
    ARCHITECTURE = "architecture"
    MATH = "math"
    RESEARCH = "research"
    PHILOSOPHY = "philosophy"
    STARTUP = "startup"
    CREATIVE = "creative"
    GENERAL = "general"


class ModelScore(BaseModel):
    """Score for a single model's response."""

    model_config = {"frozen": True}

    model_id: str
    score: float = Field(ge=0.0, le=10.0)  # 0-10 scale
    response: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class SynthesisScore(BaseModel):
    """Score for the synthesis result."""

    model_config = {"frozen": True}

    score: float = Field(ge=0.0, le=10.0)  # 0-10 scale
    unified_answer: str = ""
    agreements_found: int = 0
    contradictions_found: int = 0
    better_than_best_individual: bool = False
    improvement_pct: float = 0.0  # % improvement over best individual


class BenchmarkCase(BaseModel):
    """A single benchmark case.

    Captures the question, all responses, synthesis, and scores.
    Used to measure whether synthesis > best individual.
    """

    model_config = {"frozen": True}

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    domain: Domain = Domain.GENERAL
    question: str = ""
    success_criteria: str = ""

    # Scores
    model_scores: list[ModelScore] = Field(default_factory=list)
    synthesis_score: SynthesisScore | None = None

    # Metadata
    models_used: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def best_individual_score(self) -> float:
        if not self.model_scores:
            return 0.0
        return max(s.score for s in self.model_scores)

    @property
    def synthesis_wins(self) -> bool:
        if self.synthesis_score is None:
            return False
        return self.synthesis_score.score > self.best_individual_score

    @property
    def improvement_over_best(self) -> float:
        best = self.best_individual_score
        if best == 0 or self.synthesis_score is None:
            return 0.0
        return ((self.synthesis_score.score - best) / best) * 100


class BenchmarkResult(BaseModel):
    """Aggregated results across multiple benchmark cases."""

    model_config = {"frozen": True}

    cases: list[BenchmarkCase] = Field(default_factory=list)

    @property
    def total_cases(self) -> int:
        return len(self.cases)

    @property
    def synthesis_wins(self) -> int:
        return sum(1 for c in self.cases if c.synthesis_wins)

    @property
    def win_rate(self) -> float:
        if not self.cases:
            return 0.0
        return self.synthesis_wins / len(self.cases)

    @property
    def avg_improvement(self) -> float:
        improvements = [c.improvement_over_best for c in self.cases if c.synthesis_score]
        if not improvements:
            return 0.0
        return sum(improvements) / len(improvements)

    def by_domain(self, domain: Domain) -> BenchmarkResult:
        """Filter results by domain."""
        return BenchmarkResult(
            cases=[c for c in self.cases if c.domain == domain]
        )

    def summary(self) -> str:
        return (
            f"Win Rate: {self.win_rate:.0%} | "
            f"Avg Improvement: {self.avg_improvement:+.1f}% | "
            f"Cases: {self.total_cases}"
        )
