"""Synthesis Engine — the core value of Egregore.

V1.1: Simplified to a single LLM call.

Why single call instead of three?
- Agreement and Contradiction are byproducts of Synthesis, not separate tasks
- Fewer calls = lower latency, lower cost
- LLMs are good at multi-step reasoning in a single prompt
- We can always split later if quality suffers

Flow:
    Responses → Single Synthesizer Call → SynthesisResult
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


SYNTHESIS_PROMPT = """You are the Synthesis Engine of Egregore — a collective intelligence system.

Multiple AI models have answered the same question. Your job is to analyze their responses and produce a BETTER answer than any single model.

Original question: {prompt}

Model responses:
{responses}

Your task:
1. Find AGREEMENTS — points where models converge
2. Find CONTRADICTIONS — points where models diverge (with type: contradiction/emphasis/approach/scope)
3. SYNTHESIZE a unified answer that combines the best insights
4. Report UNCERTAINTY — what remains unknown or disputed
5. ATTRIBUTE contributions — which model contributed what

The unified answer should be BETTER than any single model's response.
It should NOT be a simple average or vote. It should take the BEST from each.

Return a JSON object:
{{
  "agreements": ["point 1", "point 2"],
  "contradictions": [
    {{
      "topic": "what they disagree about",
      "type": "contradiction",
      "models": {{"model_id": "position"}},
      "analysis": "brief explanation"
    }}
  ],
  "unified_answer": "Your synthesized answer...",
  "confidence": 0.0 to 1.0,
  "uncertainty": ["what remains unknown"],
  "contributions": [
    {{"model_id": "id", "contributions": ["insight"], "strength": "what this model did best"}}
  ]
}}

Return ONLY the JSON object, nothing else."""


class SynthesisEngine:
    """Synthesizes multiple model responses into a unified answer.

    Single LLM call. The synthesizer analyzes all responses
    and produces a SynthesisResult.
    """

    def __init__(self, synthesizer: BaseProvider) -> None:
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

        # Format responses
        formatted = self._format_responses(responses)

        # Single LLM call
        synth_prompt = SYNTHESIS_PROMPT.format(prompt=prompt, responses=formatted)
        raw = await self._call_synthesizer(synth_prompt)

        # Parse result
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("synthesis_json_parse_failed", raw=raw[:200])
            data = {
                "unified_answer": raw,
                "confidence": 0.3,
                "agreements": [],
                "contradictions": [],
                "uncertainty": ["Failed to parse structured output"],
                "contributions": [],
            }

        total_latency = (time.monotonic() - start) * 1000

        # Build result
        contradictions = []
        for c in data.get("contradictions", []):
            if isinstance(c, dict):
                contradictions.append(
                    Difference(
                        topic=c.get("topic", ""),
                        type=DifferenceType(c.get("type", "contradiction")),
                        models=c.get("models", {}),
                        analysis=c.get("analysis", ""),
                    )
                )

        result = SynthesisResult(
            prompt=prompt,
            agreements=data.get("agreements", []),
            contradictions=contradictions,
            unified_answer=data.get("unified_answer", ""),
            confidence=float(data.get("confidence", 0.0)),
            uncertainty=data.get("uncertainty", []),
            source_map=[
                SourceContribution(**c)
                for c in data.get("contributions", [])
                if isinstance(c, dict)
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
        parts = []
        for r in responses:
            model_id = r.provider_meta.provider_id if r.provider_meta else "unknown"
            parts.append(f"=== {model_id} ===\n{r.content}\n")
        return "\n".join(parts)

    async def _call_synthesizer(self, prompt: str) -> str:
        messages = [
            Message(
                role="system",
                content="You are a synthesis engine. Return only valid JSON. No markdown fences, no explanation.",
            ),
            Message(role="user", content=prompt),
        ]
        response = await self._synthesizer.complete(messages)
        return response.content.strip()
