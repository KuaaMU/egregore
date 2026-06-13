"""Tests for the Synthesis Engine.

The synthesis engine is the core value of Egregore.
These tests verify the domain models and the engine logic.
"""

import pytest

from egregore.domain.synthesis.models import (
    Difference,
    DifferenceType,
    SourceContribution,
    SynthesisResult,
)


class TestSynthesisResult:
    """Test the core entity of Egregore."""

    def test_basic_result(self):
        result = SynthesisResult(
            prompt="What is 2+2?",
            agreements=["All models agree the answer is 4"],
            unified_answer="The answer is 4.",
            confidence=0.99,
        )
        assert result.has_agreements
        assert not result.has_contradictions
        assert result.confidence_label == "Very High"

    def test_result_with_contradictions(self):
        result = SynthesisResult(
            prompt="Best language?",
            agreements=["All agree both are good"],
            contradictions=[
                Difference(
                    topic="Performance",
                    type=DifferenceType.CONTRADICTION,
                    models={"gpt": "Rust", "claude": "Go"},
                    analysis="Different priorities",
                )
            ],
            unified_answer="Depends on context.",
            confidence=0.6,
        )
        assert result.has_contradictions
        assert result.contradiction_count == 1
        assert result.confidence_label == "Moderate"

    def test_confidence_labels(self):
        cases = [
            (0.95, "Very High"),
            (0.8, "High"),
            (0.6, "Moderate"),
            (0.4, "Low"),
            (0.1, "Very Low"),
        ]
        for confidence, expected in cases:
            result = SynthesisResult(confidence=confidence)
            assert result.confidence_label == expected, f"{confidence} should be {expected}"

    def test_summary(self):
        result = SynthesisResult(
            agreements=["A", "B"],
            contradictions=[
                Difference(topic="X", type=DifferenceType.CONTRADICTION, models={})
            ],
            confidence=0.7,
        )
        summary = result.summary()
        assert "2 agreements" in summary
        assert "1 contradictions" in summary
        assert "High" in summary

    def test_result_is_frozen(self):
        result = SynthesisResult(unified_answer="test")
        with pytest.raises(Exception):
            result.unified_answer = "changed"

    def test_difference_types(self):
        assert DifferenceType.CONTRADICTION.value == "contradiction"
        assert DifferenceType.EMPHASIS.value == "emphasis"
        assert DifferenceType.APPROACH.value == "approach"
        assert DifferenceType.SCOPE.value == "scope"
        assert DifferenceType.UNCERTAINTY.value == "uncertainty"

    def test_source_contribution(self):
        sc = SourceContribution(
            model_id="gpt-4o",
            contributions=["Memory safety analysis", "Performance benchmarks"],
            strength="Engineering rigor",
            weight=0.8,
        )
        assert sc.model_id == "gpt-4o"
        assert len(sc.contributions) == 2

    def test_empty_result(self):
        result = SynthesisResult()
        assert not result.has_agreements
        assert not result.has_contradictions
        assert result.confidence == 0.0
        assert result.summary() == "confidence: Very Low"
