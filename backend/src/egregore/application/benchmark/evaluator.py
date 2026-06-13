"""Benchmark Evaluator — measures whether synthesis > best individual.

This is the most important test in Egregore. It answers:
"Does collective intelligence actually emerge?"

Pattern: Evaluator / Judge

The evaluator:
1. Takes a question + success criteria
2. Dispatches to multiple models
3. Synthesizes
4. Scores each response AND the synthesis
5. Compares synthesis vs best individual

The scorer is another LLM call — we use AI to judge AI.
This is standard practice (see: LMSYS Chatbot Arena, MT-Bench).
"""

from __future__ import annotations

import json
import time

import structlog

from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.application.synthesis.engine import SynthesisEngine
from egregore.domain.benchmark.models import (
    BenchmarkCase,
    BenchmarkResult,
    Domain,
    ModelScore,
    SynthesisScore,
)
from egregore.domain.entities.message import Message
from egregore.domain.providers.base import BaseProvider

logger = structlog.get_logger()


SCORING_PROMPT = """You are an expert evaluator scoring AI responses.

Question: {question}
Success Criteria: {criteria}

Response to score:
{response}

Score this response on a 0-10 scale considering:
- Accuracy and correctness
- Completeness
- Clarity and structure
- Practical value
- Insight quality

Return a JSON object:
{{
  "score": 0-10,
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1"]
}}

Return ONLY the JSON."""


COMPARISON_PROMPT = """You are comparing a synthesized answer against individual model answers.

Question: {question}
Success Criteria: {criteria}

Best individual answer (score: {best_score}/10):
{best_response}

Synthesized answer:
{synthesis_response}

Was the synthesis better than the best individual? By how much?

Return a JSON object:
{{
  "synthesis_score": 0-10,
  "better_than_best": true/false,
  "improvement_pct": 0-100,
  "reasoning": "why"
}}

Return ONLY the JSON."""


class BenchmarkEvaluator:
    """Evaluates whether synthesis produces better answers.

    Usage:
        evaluator = BenchmarkEvaluator(orchestrator, synthesis, judge)
        result = await evaluator.run_benchmark(cases)
    """

    def __init__(
        self,
        orchestrator: RoundTableOrchestrator,
        synthesis: SynthesisEngine,
        judge: BaseProvider,
    ) -> None:
        self._orchestrator = orchestrator
        self._synthesis = synthesis
        self._judge = judge

    async def evaluate_case(
        self,
        question: str,
        domain: Domain = Domain.GENERAL,
        criteria: str = "",
    ) -> BenchmarkCase:
        """Evaluate a single benchmark case.

        1. Round table → get responses
        2. Synthesize → get SynthesisResult
        3. Score each response
        4. Score synthesis
        5. Compare
        """
        start = time.monotonic()

        # Step 1: Round table
        rt_result = await self._orchestrator.execute(question)
        responses = [r.message for r in rt_result.results if r.success and r.message]

        if len(responses) < 2:
            logger.warning("insufficient_responses", count=len(responses))
            return BenchmarkCase(
                domain=domain,
                question=question,
                success_criteria=criteria,
            )

        # Step 2: Synthesis
        synthesis_result = await self._synthesis.synthesize(question, responses)

        # Step 3: Score each response
        model_scores = []
        for r in responses:
            model_id = r.provider_meta.provider_id if r.provider_meta else "unknown"
            score = await self._score_response(question, criteria, r.content)
            model_scores.append(
                ModelScore(
                    model_id=model_id,
                    score=score.get("score", 5.0),
                    response=r.content,
                    strengths=score.get("strengths", []),
                    weaknesses=score.get("weaknesses", []),
                )
            )

        # Step 4+5: Score synthesis and compare
        best_score = max(s.score for s in model_scores) if model_scores else 0
        best_response = max(model_scores, key=lambda s: s.score).response if model_scores else ""

        comparison = await self._compare_synthesis(
            question, criteria, best_score, best_response, synthesis_result.unified_answer
        )

        synthesis_score = SynthesisScore(
            score=comparison.get("synthesis_score", best_score),
            unified_answer=synthesis_result.unified_answer,
            agreements_found=synthesis_result.agreement_count,
            contradictions_found=synthesis_result.contradiction_count,
            better_than_best_individual=comparison.get("better_than_best", False),
            improvement_pct=comparison.get("improvement_pct", 0.0),
        )

        elapsed = (time.monotonic() - start) * 1000

        case = BenchmarkCase(
            domain=domain,
            question=question,
            success_criteria=criteria,
            model_scores=model_scores,
            synthesis_score=synthesis_score,
            models_used=[r.provider_meta.provider_id for r in responses if r.provider_meta],
        )

        logger.info(
            "benchmark_case_complete",
            domain=domain,
            synthesis_wins=case.synthesis_wins,
            improvement=case.improvement_over_best,
            latency_ms=elapsed,
        )

        return case

    async def _score_response(self, question: str, criteria: str, response: str) -> dict:
        """Score a single response using the judge model."""
        prompt = SCORING_PROMPT.format(
            question=question,
            criteria=criteria or "General quality",
            response=response,
        )
        try:
            raw = await self._call_judge(prompt)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("scoring_failed", error=str(e))
            return {"score": 5.0, "strengths": [], "weaknesses": []}

    async def _compare_synthesis(
        self,
        question: str,
        criteria: str,
        best_score: float,
        best_response: str,
        synthesis_response: str,
    ) -> dict:
        """Compare synthesis against best individual."""
        prompt = COMPARISON_PROMPT.format(
            question=question,
            criteria=criteria or "General quality",
            best_score=best_score,
            best_response=best_response,
            synthesis_response=synthesis_response,
        )
        try:
            raw = await self._call_judge(prompt)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("comparison_failed", error=str(e))
            return {
                "synthesis_score": best_score,
                "better_than_best": False,
                "improvement_pct": 0.0,
            }

    async def _call_judge(self, prompt: str) -> str:
        messages = [
            Message(role="system", content="You are an expert evaluator. Return only valid JSON."),
            Message(role="user", content=prompt),
        ]
        response = await self._judge.complete(messages)
        return response.content.strip()
