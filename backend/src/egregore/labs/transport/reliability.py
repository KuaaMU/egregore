"""Reliability Test — measures ChatGPT adapter reliability over time.

Usage:
    uv run python -m egregore.labs.transport.reliability [hours] [interval_seconds]

Defaults: 72h, 300s (5 min) interval.

This will:
1. Launch ChatGPT adapter
2. Send prompts every N minutes
3. Track success/failure/latency/failure_type
4. Print stats every 10 prompts
5. Save results to JSON

Success criteria:
- 72h runtime
- 1000+ requests
- 95% success rate
- Failure breakdown tells us what to fix
"""

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTAdapter

TEST_PROMPTS = [
    "What is 2+2?",
    "Name three programming languages.",
    "What is the capital of Japan?",
    "Explain recursion in one sentence.",
    "What color is the sky?",
    "Name a mammal that can fly.",
    "What is 10 * 15?",
    "What day comes after Monday?",
    "What is the boiling point of water?",
    "Name two rivers in Africa.",
]

RESULTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "benchmarks" / "reliability"


def classify_failure(error: str, response: str = "") -> str:
    """Classify the type of failure.

    This is the data we need to decide what to build next.
    """
    error_lower = error.lower()

    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "selector" in error_lower or "locator" in error_lower or "not found" in error_lower:
        return "selector_error"
    if "login" in error_lower or "sign in" in error_lower or "auth" in error_lower:
        return "login_expired"
    if "captcha" in error_lower or "verify" in error_lower:
        return "captcha"
    if "network" in error_lower or "connection" in error_lower or "fetch" in error_lower:
        return "network_error"
    if "rate limit" in error_lower or "too many" in error_lower:
        return "rate_limited"
    if response == "":
        return "empty_response"
    return "unknown"


async def run_reliability_test(
    duration_hours: float = 72.0,
    interval_seconds: float = 300.0,
) -> None:
    """Run the reliability test."""
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

    print(f"Reliability test: {duration_hours}h, interval {interval_seconds}s")
    print(f"Results: {results_file}")
    print(f"Target: 1000+ requests, 95% success rate")
    print()

    try:
        while time.monotonic() < end_time:
            prompt = TEST_PROMPTS[prompt_index % len(TEST_PROMPTS)]
            prompt_index += 1
            total += 1

            # Health check
            healthy = await adapter.health_check()

            if not healthy:
                failures += 1
                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": prompt,
                    "success": False,
                    "error": "health_check_failed",
                    "failure_type": "health_check_failed",
                    "latency_ms": 0,
                })
                print(f"  [{total}] FAIL: health_check_failed")
                # Attempt recovery: close and relaunch
                await adapter.close()
                await asyncio.sleep(5)
                try:
                    await adapter.launch()
                except Exception as e:
                    print(f"  [{total}] RECOVERY FAILED: {e}")
                continue

            # Send prompt
            start = time.monotonic()
            try:
                response = await adapter.send(prompt, timeout_ms=60000)
                latency_ms = (time.monotonic() - start) * 1000

                if len(response) > 0:
                    successes += 1
                    results.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "prompt": prompt,
                        "response_length": len(response),
                        "success": True,
                        "latency_ms": latency_ms,
                    })
                    print(f"  [{total}] OK: {len(response)} chars, {latency_ms:.0f}ms")
                else:
                    failures += 1
                    results.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "prompt": prompt,
                        "success": False,
                        "error": "empty_response",
                        "failure_type": "empty_response",
                        "latency_ms": latency_ms,
                    })
                    print(f"  [{total}] FAIL: empty_response, {latency_ms:.0f}ms")

            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                failures += 1
                failure_type = classify_failure(str(e))
                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": prompt,
                    "success": False,
                    "error": str(e)[:200],
                    "failure_type": failure_type,
                    "latency_ms": latency_ms,
                })
                print(f"  [{total}] FAIL [{failure_type}]: {str(e)[:80]}")

            # Stats every 10 prompts
            if total % 10 == 0:
                _print_stats(results, successes, failures, total, start_time)
                _save_results(results_file, results, start_time)

            await asyncio.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        await adapter.close()
        _save_results(results_file, results, start_time)
        _print_final(results, successes, failures, total, start_time, results_file)


def _print_stats(results: list, successes: int, failures: int, total: int, start_time: float):
    """Print intermediate stats with failure breakdown."""
    rate = successes / total if total > 0 else 0
    avg_latency = sum(r["latency_ms"] for r in results if r["success"]) / max(successes, 1)
    elapsed_h = (time.monotonic() - start_time) / 3600

    print(f"\n  {'='*50}")
    print(f"  Stats after {total} requests ({elapsed_h:.1f}h)")
    print(f"  Success rate: {rate:.1%} ({successes}/{total})")
    print(f"  Avg latency: {avg_latency:.0f}ms")

    # Failure breakdown
    failure_types = {}
    for r in results:
        if not r["success"]:
            ft = r.get("failure_type", "unknown")
            failure_types[ft] = failure_types.get(ft, 0) + 1

    if failure_types:
        print(f"  Failure breakdown:")
        for ft, count in sorted(failure_types.items(), key=lambda x: -x[1]):
            print(f"    {ft}: {count}")

    print(f"  {'='*50}\n")


def _print_final(results: list, successes: int, failures: int, total: int, start_time: float, results_file: Path):
    """Print final summary."""
    rate = successes / total if total > 0 else 0
    elapsed_h = (time.monotonic() - start_time) / 3600

    print(f"\n{'='*60}")
    print(f"FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Duration: {elapsed_h:.1f}h")
    print(f"Total requests: {total}")
    print(f"Successes: {successes}")
    print(f"Failures: {failures}")
    print(f"Success rate: {rate:.1%}")
    print(f"Target: 95% — {'PASS ✓' if rate >= 0.95 else 'FAIL ✗'}")

    # Failure breakdown
    failure_types = {}
    for r in results:
        if not r["success"]:
            ft = r.get("failure_type", "unknown")
            failure_types[ft] = failure_types.get(ft, 0) + 1

    if failure_types:
        print(f"\nFailure Breakdown:")
        print(f"  {'Type':<20} {'Count':>6}")
        print(f"  {'-'*26}")
        for ft, count in sorted(failure_types.items(), key=lambda x: -x[1]):
            print(f"  {ft:<20} {count:>6}")

    print(f"\nResults: {results_file}")


def _save_results(path: Path, results: list, start_time: float):
    """Save results to JSON with failure breakdown."""
    successes = sum(1 for r in results if r["success"])
    total = len(results)

    failure_types = {}
    for r in results:
        if not r["success"]:
            ft = r.get("failure_type", "unknown")
            failure_types[ft] = failure_types.get(ft, 0) + 1

    data = {
        "summary": {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0,
            "elapsed_hours": (time.monotonic() - start_time) / 3600,
            "failure_breakdown": failure_types,
        },
        "results": results,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 72.0
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
    asyncio.run(run_reliability_test(hours, interval))
