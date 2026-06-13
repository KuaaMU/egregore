"""Synthesis Engine — the core value of Egregore.

This is NOT voting. This is NOT majority rule.

The Synthesis Engine:
1. Receives responses from multiple models
2. Detects agreements (what they all see)
3. Detects contradictions (where they diverge)
4. Synthesizes a unified answer (better than any individual)
5. Reports uncertainty (what remains unknown)

The synthesis is done by ANOTHER model (the Synthesizer).
This is deliberate: we use AI to analyze AI responses.

Why not embeddings/clustering/graphs?
- Simple is better for V1
- LLMs are good at understanding text
- We can always add sophistication later
- The magic moment comes from synthesis quality, not algorithm complexity

Flow:
    Responses → Agreement Detector → Contradiction Detector → Synthesizer → Result

Each step is an LLM call with a specific prompt.
"""

from __future__ import annotations

import json
import time

import structlog

from egregore.domain.entities.message import Message
from egregore.domain.providers.base import BaseProvider
from egregore.domain.synthesis.models import (
    Difference,
    DifferenceType,
    SourceContribution,
    SynthesisResult,
)

logger = structlog.get_logger()


# === Prompts ===

AGREEMENT_PROMPT = """You are analyzing responses from multiple AI models to the same question.

Your task: Find points of AGREEMENT — things all or most models agree on.

Models and their responses:
{responses}

Return a JSON array of agreement points. Each point should be a clear, concise statement.
Only include points where 2+ models explicitly agree.

Example:
["All models agree that X is the best approach", "Models converge on Y being a key factor"]

Return ONLY the JSON array, nothing else."""

CONTRADICTION_PROMPT = """You are analyzing responses from multiple AI models to the same question.

Your task: Find CONTRADICTIONS and significant DIFFERENCES — places where models disagree or emphasize different things.

Models and their responses:
{responses}

Return a JSON array of differences. Each difference should have:
- topic: what they disagree about
- type: one of "contradiction", "emphasis", "approach", "scope", "uncertainty"
- models: object mapping model_id to their position
- analysis: brief explanation

Example:
[
  {
    "topic": "Time Complexity",
    "type": "contradiction",
    "models": {"gpt": "O(n log n)", "claude": "O(n)"},
    "analysis": "Different algorithms suggested"
  }
]

Return ONLY the JSON array, nothing else."""

SYNTHESIS_PROMPT = """You are the Synthesis Engine of Egregore — a collective intelligence system.

Multiple AI models have answered the same question. Your job is to produce a BETTER answer than any individual model by taking the best from each.

Original question: {prompt}

Model responses:
{responses}

Agreements found:
{agreements}

Contradictions found:
{contradictions}

Your task:
1. Write a unified answer that combines the best insights from all models
2. The answer should be BETTER than any single model's response
3. Resolve contradictions where possible, acknowledge them where not
4. Be specific and actionable

Return a JSON object:
{{
  "unified_answer": "Your synthesized answer here...",
  "confidence": 0.0 to 1.0,
  "uncertainty": ["What remains unknown or disputed"],
  "contributions": [
    {{"model_id": "gpt-4o", "contributions": ["insight 1"], "strength": "what this model did best"}},
    {{"model_id": "claude", "contributions": ["insight 2"], "strength": "what this model did best"}}
  ]
}}

Return ONLY the JSON object, nothing else."""


class SynthesisEngine:
    """Orchestrates the synthesis of multiple model responses.

    This is the core of Egregore. It takes raw responses and
    produces a SynthesisResult — the emergent intelligence.

    Usage:
        engine = SynthesisEngine(synthesizer_provider)
        result = await engine.synthesize(prompt, responses)
    """

    def __init__(self, synthesizer: BaseProvider) -> None:
        """
        Args:
            synthesizer: The model used to analyze and synthesize responses.
                         Typically a fast, cheap model (GPT-4o-mini, Qwen3, etc.)
        """
        self._synthesizer = synthesizer

    async def synthesize(
        self,
        prompt: str,
        responses: list[Message],
    ) -> SynthesisResult:
        """Synthesize multiple responses into a unified answer.

        Args:
            prompt: The original question
            responses: List of provider responses (role=PROVIDER)

        Returns:
            SynthesisResult with agreements, contradictions, unified answer
        """
        start = time.monotonic()

        # Format responses for prompts
        formatted = self._format_responses(responses)

        # Step 1: Detect agreements
        agreements = await self._detect_agreements(formatted)
        logger.info("agreements_detected", count=len(agreements))

        # Step 2: Detect contradictions
        contradictions = await self._detect_contradictions(formatted)
        logger.info("contradictions_detected", count=len(contradictions))

        # Step 3: Synthesize
        synthesis = await self._synthesize(prompt, formatted, agreements, contradictions)

        total_latency = (time.monotonic() - start) * 1000

        result = SynthesisResult(
            prompt=prompt,
            agreements=agreements,
            contradictions=contradictions,
            unified_answer=synthesis.get("unified_answer", ""),
            confidence=synthesis.get("confidence", 0.0),
            uncertainty=synthesis.get("uncertainty", []),
            source_map=[
                SourceContribution(**c) for c in synthesis.get("contributions", [])
            ],
            models_used=[r.provider_meta.provider_id for r in responses if r.provider_meta],
            total_latency_ms=total_latency,
        )

        logger.info(
            "synthesis_complete",
            agreements=result.agreement_count,
            contradictions=result.contradiction_count,
            confidence=result.confidence,
            latency_ms=total_latency,
        )

        return result

    def _format_responses(self, responses: list[Message]) -> str:
        """Format responses into a readable string for prompts."""
        parts = []
        for r in responses:
            model_id = r.provider_meta.provider_id if r.provider_meta else "unknown"
            parts.append(f"=== {model_id} ===\n{r.content}\n")
        return "\n".join(parts)

    async def _detect_agreements(self, formatted_responses: str) -> list[str]:
        """Call the synthesizer to detect agreements."""
        prompt = AGREEMENT_PROMPT.format(responses=formatted_responses)
        try:
            response = await self._call_synthesizer(prompt)
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("agreement_detection_failed", error=str(e))
        return []

    async def _detect_contradictions(self, formatted_responses: str) -> list[Difference]:
        """Call the synthesizer to detect contradictions."""
        prompt = CONTRADICTION_PROMPT.format(responses=formatted_responses)
        try:
            response = await self._call_synthesizer(prompt)
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [
                    Difference(
                        topic=item.get("topic", ""),
                        type=DifferenceType(item.get("type", "contradiction")),
                        models=item.get("models", {}),
                        analysis=item.get("analysis", ""),
                    )
                    for item in parsed
                    if isinstance(item, dict)
                ]
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("contradiction_detection_failed", error=str(e))
        return []

    async def _synthesize(
        self,
        prompt: str,
        formatted_responses: str,
        agreements: list[str],
        contradictions: list[Difference],
    ) -> dict:
        """Call the synthesizer to produce the unified answer."""
        agreements_text = "\n".join(f"- {a}" for a in agreements) if agreements else "None found"
        contradictions_text = (
            "\n".join(
                f"- {c.topic}: {c.analysis}"
                for c in contradictions
            )
            if contradictions
            else "None found"
        )

        prompt_text = SYNTHESIS_PROMPT.format(
            prompt=prompt,
            responses=formatted_responses,
            agreements=agreements_text,
            contradictions=contradictions_text,
        )

        try:
            response = await self._call_synthesizer(prompt_text)
            return json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("synthesis_failed", error=str(e))
            return {
                "unified_answer": "Synthesis failed. Please review individual responses.",
                "confidence": 0.0,
                "uncertainty": ["Synthesis engine error"],
                "contributions": [],
            }

    async def _call_synthesizer(self, prompt: str) -> str:
        """Call the synthesizer model with a prompt.

        Uses the provider's complete() method.
        Wraps the prompt in a system message for better results.
        """
        messages = [
            Message(
                role="system",
                content="You are a synthesis engine. Return only valid JSON. No markdown, no explanation.",
            ),
            Message(role="user", content=prompt),
        ]
        response = await self._synthesizer.complete(messages)
        return response.content.strip()
