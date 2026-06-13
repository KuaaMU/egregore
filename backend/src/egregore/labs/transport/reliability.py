"""Reliability Test — measures ChatGPT adapter reliability over time.

Run this to test 24h reliability.

Usage:
    uv run python -m egregore.labs.transport.reliability

This will:
1. Launch ChatGPT adapter
2. Send prompts every N minutes
3. Track success/failure/latency
4. Print stats every hour
5. Save results to JSON

Success criteria:
- 24h runtime
- 95% success rate
- Average latency < 30s
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTAdapter

# Test prompts — rotate through these
TEST_PROMPTS = [
    "What is 2+2?",
    "Name three programming languages.",
    "What is the capital of Japan?",
    "Explain recursion in one sentence.",
    "What color is the sky?",
    "Name a mammal that can fly.",
    "What is 10 * 15?",
    "What day comes after Monday?",
]

# Output file
RESULTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "benchmarks" / "reliability"


async def run_reliability_test(
    duration_hours: float = 24.0,
    interval_seconds: float = 300.0,  # 5 minutes
) -> None:
    """Run the reliability test.

    Args:
        duration_hours: How long to run (default 24h)
        interval_seconds: Seconds between prompts (default 5 min)
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = RESULTS_DIR / f"reliability_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    adapter = ChatGPTAdapter(headless=True)
    await adapter.launch()

    results = []
    start_time = time.monotonic()
    end_time = start_time + (duration_hours * 3600)
    prompt_index = 0
    total = 0
    successes = 0
    failures = 0

    print(f"Starting reliability test: {duration_hours}h, interval {interval_seconds}s")
    print(f"Results will be saved to: {results_file}")
    print()

    try:
        while time.monotonic() < end_time:
            prompt = TEST_PROMPTS[prompt_index % len(TEST_PROMPTS)]
            prompt_index += 1
            total += 1

            # Health check first
            healthy = await adapter.health_check()

            if not healthy:
                failures += 1
                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": prompt,
                    "success": False,
                    "error": "health_check_failed",
                    "latency_ms": 0,
                })
                print(f"  [{total}] FAIL: health check failed")
                # Try to recover
                await adapter.close()
                await asyncio.sleep(5)
                await adapter.launch()
                continue

            # Send prompt
            start = time.monotonic()
            try:
                response = await adapter.send(prompt, timeout_ms=60000)
                latency_ms = (time.monotonic() - start) * 1000
                success = len(response) > 0

                if success:
                    successes += 1
                else:
                    failures += 1

                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": prompt,
                    "response_length": len(response),
                    "success": success,
                    "latency_ms": latency_ms,
                })

                status = "OK" if success else "EMPTY"
                print(f"  [{total}] {status}: {len(response)} chars, {latency_ms:.0f}ms")

            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                failures += 1
                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": prompt,
                    "success": False,
                    "error": str(e),
                    "latency_ms": latency_ms,
                })
                print(f"  [{total}] ERROR: {e}")

            # Print stats every 10 prompts
            if total % 10 == 0:
                rate = successes / total if total > 0 else 0
                avg_latency = sum(r["latency_ms"] for r in results if r["success"]) / max(successes, 1)
                elapsed_h = (time.monotonic() - start_time) / 3600
                print(f"\n  Stats after {total} prompts ({elapsed_h:.1f}h):")
                print(f"    Success rate: {rate:.1%}")
                print(f"    Avg latency: {avg_latency:.0f}ms")
                print(f"    Successes: {successes}, Failures: {failures}")
                print()

                # Save intermediate results
                _save_results(results_file, results, start_time)

            # Wait for next interval
            await asyncio.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")

    finally:
        await adapter.close()

        # Save final results
        _save_results(results_file, results, start_time)

        # Print final summary
        rate = successes / total if total > 0 else 0
        print(f"\n{'='*60}")
        print(f"FINAL RESULTS")
        print(f"{'='*60}")
        print(f"Duration: {(time.monotonic() - start_time) / 3600:.1f}h")
        print(f"Total prompts: {total}")
        print(f"Successes: {successes}")
        print(f"Failures: {failures}")
        print(f"Success rate: {rate:.1%}")
        print(f"Target: 95% — {'PASS' if rate >= 0.95 else 'FAIL'}")
        print(f"Results: {results_file}")


def _save_results(path: Path, results: list, start_time: float) -> None:
    """Save results to JSON."""
    successes = sum(1 for r in results if r["success"])
    total = len(results)
    data = {
        "summary": {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0,
            "elapsed_hours": (time.monotonic() - start_time) / 3600,
        },
        "results": results,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    asyncio.run(run_reliability_test(hours, interval))
