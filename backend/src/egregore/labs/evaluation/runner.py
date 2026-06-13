"""Benchmark Runner — executes benchmark cases and produces results.

Run with:
    uv run python -m egregore.labs.evaluation.runner

This will:
1. Run all benchmark cases
2. Score each response
3. Compare synthesis vs best individual
4. Print results table
5. Save results to JSON

The goal: prove that Synthesis > Best Individual > 70% of the time.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import structlog

from egregore.application.benchmark.evaluator import BenchmarkEvaluator
from egregore.application.orchestrators.round_table import RoundTableOrchestrator
from egregore.application.synthesis.engine import SynthesisEngine
from egregore.config.settings import settings
from egregore.domain.benchmark.models import BenchmarkResult, Domain
from egregore.domain.events.bus import EventBus
from egregore.domain.providers.base import ProviderConfig
from egregore.domain.providers.registry import ProviderRegistry
from egregore.infrastructure.providers.mock import MockProvider
from egregore.labs.evaluation.cases import BENCHMARK_CASES

logger = structlog.get_logger()

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "benchmarks" / "results"


async def run_benchmark(max_cases: int = 0) -> BenchmarkResult:
    """Run the benchmark suite.

    Args:
        max_cases: Maximum number of cases to run (0 = all)
    """
    # Set up dependencies
    event_bus = EventBus()
    registry = ProviderRegistry()

    # Register providers
    _register_providers(registry)

    orchestrator = RoundTableOrchestrator(registry=registry, event_bus=event_bus)
    synthesis = _create_synthesis()
    judge = _create_judge()

    evaluator = BenchmarkEvaluator(orchestrator, synthesis, judge)

    # Run cases
    cases = BENCHMARK_CASES
    if max_cases > 0:
        cases = cases[:max_cases]

    results = []
    for i, (question, domain, criteria) in enumerate(cases):
        logger.info("running_case", index=i + 1, total=len(cases), domain=domain)
        case = await evaluator.evaluate_case(question, domain, criteria)
        results.append(case)

        # Print progress
        print(f"  [{i+1}/{len(cases)}] {domain.value}: "
              f"{'WIN' if case.synthesis_wins else 'LOSS'} "
              f"(improvement: {case.improvement_over_best:+.1f}%)")

    benchmark_result = BenchmarkResult(cases=results)

    # Print summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(benchmark_result.summary())
    print(f"\nBy domain:")
    for domain in Domain:
        dr = benchmark_result.by_domain(domain)
        if dr.total_cases > 0:
            print(f"  {domain.value}: {dr.summary()}")

    # Save results
    _save_results(benchmark_result)

    return benchmark_result


def _register_providers(registry: ProviderRegistry) -> None:
    """Register providers for benchmarking."""
    if settings.openai_api_key:
        from egregore.infrastructure.providers.openai_provider import OpenAIProvider

        registry.register(OpenAIProvider(
            config=ProviderConfig(provider_id="gpt-4o", model=settings.openai_model, api_key=settings.openai_api_key)
        ))

    if settings.anthropic_api_key:
        from egregore.infrastructure.providers.anthropic_provider import AnthropicProvider

        registry.register(AnthropicProvider(
            config=ProviderConfig(provider_id="claude", model=settings.anthropic_model, api_key=settings.anthropic_api_key)
        ))

    # Always add mock for development
    if len(registry) < 2:
        logger.warning("insufficient_providers", action="adding_mocks")
        _add_mock_providers(registry)


def _add_mock_providers(registry: ProviderRegistry) -> None:
    """Add mock providers with diverse perspectives."""
    mocks = [
        ("mock-gpt4", "gpt-4o-sim",
         "From an engineering perspective, I'd recommend Rust for this use case. "
         "The memory safety guarantees without garbage collection make it ideal for "
         "systems programming. The learning curve is steep but the long-term benefits "
         "are significant. Consider using Tokio for async runtime."),
        ("mock-claude", "claude-sim",
         "I'd approach this differently. While Rust has clear performance advantages, "
         "Go offers a better balance of simplicity and performance for most teams. "
         "The goroutine model is elegant for concurrent workloads, and the ecosystem "
         "is mature. Unless you need zero-cost abstractions, Go is the pragmatic choice."),
        ("mock-llama", "llama-sim",
         "Both Rust and Go are excellent choices. For your specific requirements, "
         "I'd suggest starting with Go for the rapid prototyping phase, then evaluating "
         "whether performance-critical components need Rust. A hybrid approach often "
         "works best in practice. Consider the team's existing expertise."),
    ]
    for pid, model, response in mocks:
        registry.register(MockProvider(
            config=ProviderConfig(provider_id=pid, model=model),
            response=response,
            latency_ms=150.0 + hash(pid) % 200,
        ))


def _create_synthesis() -> SynthesisEngine:
    """Create synthesis engine."""
    if settings.openai_api_key:
        from egregore.infrastructure.providers.openai_provider import OpenAIProvider
        return SynthesisEngine(synthesizer=OpenAIProvider(
            config=ProviderConfig(provider_id="synth", model="gpt-4o-mini", api_key=settings.openai_api_key)
        ))
    if settings.anthropic_api_key:
        from egregore.infrastructure.providers.anthropic_provider import AnthropicProvider
        return SynthesisEngine(synthesizer=AnthropicProvider(
            config=ProviderConfig(provider_id="synth", model="claude-haiku-4-5-20251001", api_key=settings.anthropic_api_key)
        ))
    return SynthesisEngine(synthesizer=MockProvider(
        config=ProviderConfig(provider_id="synth", model="mock-synth"),
        response='{"agreements": ["Both languages are viable"], "contradictions": [{"topic": "Primary choice", "type": "contradiction", "models": {"gpt": "Rust", "claude": "Go"}, "analysis": "Different priorities"}], "unified_answer": "Consider a hybrid: Go for prototyping, Rust for performance-critical paths.", "confidence": 0.75, "uncertainty": ["Team expertise not considered"], "contributions": [{"model_id": "gpt", "contributions": ["Performance analysis"], "strength": "Engineering"}, {"model_id": "claude", "contributions": ["Pragmatic tradeoffs"], "strength": "Practical"}]}',
    ))


def _create_judge():
    """Create judge model for scoring."""
    if settings.openai_api_key:
        from egregore.infrastructure.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(
            config=ProviderConfig(provider_id="judge", model="gpt-4o-mini", api_key=settings.openai_api_key)
        )
    return MockProvider(
        config=ProviderConfig(provider_id="judge", model="mock-judge"),
        response='{"score": 8.0, "strengths": ["Good analysis"], "weaknesses": ["Could be more specific"]}',
    )


def _save_results(result: BenchmarkResult) -> None:
    """Save benchmark results to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "benchmark_result.json"

    data = {
        "summary": {
            "total_cases": result.total_cases,
            "synthesis_wins": result.synthesis_wins,
            "win_rate": result.win_rate,
            "avg_improvement": result.avg_improvement,
        },
        "cases": [
            {
                "question": c.question,
                "domain": c.domain.value,
                "best_individual": c.best_individual_score,
                "synthesis": c.synthesis_score.score if c.synthesis_score else None,
                "synthesis_wins": c.synthesis_wins,
                "improvement": c.improvement_over_best,
            }
            for c in result.cases
        ],
    }

    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    max_cases = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    asyncio.run(run_benchmark(max_cases=max_cases))
