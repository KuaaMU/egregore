"""NoOpSynthesizer — returns raw responses, no synthesis.

Used during Dogfooding phase. Collects data without processing.
"""

from egregore.synthesis.base import SynthesisResult


class NoOpSynthesizer:
    """Does nothing. Returns raw responses as-is."""

    def synthesize(self, prompt: str, responses: dict[str, str]) -> SynthesisResult:
        return SynthesisResult(
            provider_summaries={pid: text[:200] for pid, text in responses.items()},
            common_points=[],
            differences=[],
            unified_answer="",
            confidence=0.0,
        )
