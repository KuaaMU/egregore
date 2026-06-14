"""Synthesizer — interface for future synthesis.

Defined now, implemented later. This decouples Round Table from Synthesis.

Implementations (future):
- NoOpSynthesizer — returns raw responses only
- LocalSynthesizer — uses local model (phi4, qwen3, etc.)
- APISynthesizer — uses API (GPT-4o-mini, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProviderSummary:
    """Summary of a single provider's response."""

    provider: str
    summary: str = ""
    key_points: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Difference:
    """A difference between providers."""

    topic: str
    providers: dict[str, str] = field(default_factory=dict)  # provider → view
    analysis: str = ""


@dataclass(frozen=True)
class SynthesisResult:
    """Result of synthesizing multiple responses."""

    provider_summaries: dict[str, str] = field(default_factory=dict)
    common_points: list[str] = field(default_factory=list)
    differences: list[Difference] = field(default_factory=list)
    unified_answer: str = ""
    confidence: float = 0.0
    uncertainty: list[str] = field(default_factory=list)


@runtime_checkable
class Synthesizer(Protocol):
    """Interface for synthesis implementations."""

    def synthesize(self, prompt: str, responses: dict[str, str]) -> SynthesisResult:
        """Synthesize multiple responses into a unified answer.

        Args:
            prompt: The original question
            responses: provider_id → response text

        Returns:
            SynthesisResult with summaries, agreements, differences, unified answer
        """
        ...
