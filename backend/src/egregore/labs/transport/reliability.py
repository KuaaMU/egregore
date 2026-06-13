"""Reliability Test — measures ChatGPT adapter reliability over time.

Usage:
    uv run python -m egregore.labs.transport.reliability [hours] [interval_seconds]

Stage 0: 2h, 1min, 120 requests (smoke test)
Stage 1: 12h, 3min, 240 requests
Stage 2: 72h, 5min, 864 requests
Stage 3: 7d, 10min, 1000+ requests

Success criteria:
- 95% success rate
- Selector errors = 0
- Failure breakdown tells us what to fix

On failure:
- Auto screenshot → benchmarks/screenshots/
- Auto HTML dump → benchmarks/html/
- Failure type classification
"""

import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from egregore.infrastructure.transport.chatgpt_browser import ChatGPTConnector

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

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "benchmarks"
RESULTS_DIR = BASE_DIR / "reliability"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
HTML_DIR = BASE_DIR / "html"


def classify_failure(error: str, response: str = "") -> str:
    """Classify the type of failure."""
    e = error.lower()
    if "timeout" in e or "timed out" in e:
        return "timeout"
    if "selector" in e or "locator" in e or "not found" in e or "waiting for" in e:
        return "selector_error"
    if "login" in e or "sign in" in e or "auth" in e:
        return "auth_expired"
    if "captcha" in e or "verify" in e:
        return "captcha"
    if "network" in e or "connection" in e or "fetch" in e:
        return "network_error"
    if "rate limit" in e or "too many" in e:
        return "rate_limit"
    if response == "":
        return "empty_response"
    return "unknown"


def percentile(data: list[float], p: float) -> float:
    """Calculate percentile."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


async def save_failure_artifacts(connector: ChatGPTConnector, index: int, error: str):
    """Save screenshot and HTML on failure."""
    try:
        if connector._page and not connector._page.is_closed():
            # Screenshot
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            ss_path = SCREENSHOTS_DIR / f"failure_{index:04d}.png"
            await connector._page.screenshot(path=str(ss_path))

            # HTML
            HTML_DIR.mkdir(parents=True, exist_ok=True)
            html_path = HTML_DIR / f"failure_{index:04d}.html"
            html = await connector._page.content()
            html_path.write_text(html, encoding="utf-8")

            return str(ss_path), str(html_path)
    except Exception:
        pass
    return None, None


async def run_reliability_test(
    duration_hours: float = 2.0,
    interval_seconds: float = 60.0,
) -> None:
    """Run the reliability test."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = RESULTS_DIR / f"reliability_{ts}.json"

    adapter = ChatGPTConnector()
    await adapter.connect()

    results = []
    latencies: list[float] = []
    start_time = time.monotonic()
    end_time = start_time + (duration_hours * 3600)
    prompt_index = 0
    total = 0
    successes = 0
    failures = 0

    print(f"Reliability test: {duration_hours}h, interval {interval_seconds}s")
    print(f"Results: {results_file}")
    print(f"Screenshots: {SCREENSHOTS_DIR}")
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
                ss, html = await save_failure_artifacts(adapter, total, "health_check_failed")
                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request": total,
                    "prompt": prompt,
                    "success": False,
                    "error": "health_check_failed",
                    "failure_type": "health_check_failed",
                    "latency_ms": 0,
                    "screenshot": ss,
                    "html": html,
                })
                print(f"  [{total}] FAIL: health_check_failed")
                # Recovery: close and relaunch
                await adapter.close()
                await asyncio.sleep(5)
                try:
                    await adapter.connect()
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
                    latencies.append(latency_ms)
                    results.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "request": total,
                        "prompt": prompt,
                        "response_length": len(response),
                        "success": True,
                        "latency_ms": latency_ms,
                    })
                    print(f"  [{total}] OK: {len(response)} chars, {latency_ms:.0f}ms")
                else:
                    failures += 1
                    ss, html = await save_failure_artifacts(adapter, total, "empty_response")
                    results.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "request": total,
                        "prompt": prompt,
                        "success": False,
                        "error": "empty_response",
                        "failure_type": "empty_response",
                        "latency_ms": latency_ms,
                        "screenshot": ss,
                        "html": html,
                    })
                    print(f"  [{total}] FAIL: empty_response")

            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                failures += 1
                failure_type = classify_failure(str(e))
                ss, html = await save_failure_artifacts(adapter, total, str(e))
                results.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request": total,
                    "prompt": prompt,
                    "success": False,
                    "error": str(e)[:200],
                    "failure_type": failure_type,
                    "latency_ms": latency_ms,
                    "screenshot": ss,
                    "html": html,
                })
                print(f"  [{total}] FAIL [{failure_type}]: {str(e)[:80]}")

            # Stats every 10 requests
            if total % 10 == 0:
                _print_stats(results, successes, failures, total, latencies, start_time)
                _save_results(results_file, results, latencies, start_time)

            await asyncio.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        await adapter.close()
        _save_results(results_file, results, latencies, start_time)
        _print_final(results, successes, failures, total, latencies, start_time, results_file)


def _print_stats(results: list, successes: int, failures: int, total: int, latencies: list, start_time: float):
    """Print intermediate stats."""
    rate = successes / total if total > 0 else 0
    elapsed_h = (time.monotonic() - start_time) / 3600

    print(f"\n  {'='*55}")
    print(f"  Stats after {total} requests ({elapsed_h:.1f}h)")
    print(f"  Success rate: {rate:.1%} ({successes}/{total})")

    if latencies:
        print(f"  Latency: p50={percentile(latencies, 50):.0f}ms  p95={percentile(latencies, 95):.0f}ms  p99={percentile(latencies, 99):.0f}ms")

    # Failure breakdown
    failure_types = {}
    for r in results:
        if not r["success"]:
            ft = r.get("failure_type", "unknown")
            failure_types[ft] = failure_types.get(ft, 0) + 1

    if failure_types:
        print(f"  Failures:")
        for ft, count in sorted(failure_types.items(), key=lambda x: -x[1]):
            print(f"    {ft}: {count}")

    print(f"  {'='*55}\n")


def _print_final(results: list, successes: int, failures: int, total: int, latencies: list, start_time: float, results_file: Path):
    """Print final report."""
    rate = successes / total if total > 0 else 0
    elapsed_h = (time.monotonic() - start_time) / 3600

    print(f"\n{'='*60}")
    print(f"EGREGORE TRANSPORT RELIABILITY REPORT")
    print(f"{'='*60}")
    print(f"Duration:     {elapsed_h:.1f}h")
    print(f"Requests:     {total}")
    print(f"Successes:    {successes}")
    print(f"Failures:     {failures}")
    print(f"Success rate: {rate:.1%}")
    print(f"Target:       95% — {'PASS' if rate >= 0.95 else 'FAIL'}")

    if latencies:
        print(f"\nLatency:")
        print(f"  p50: {percentile(latencies, 50):.1f}s")
        print(f"  p95: {percentile(latencies, 95):.1f}s")
        print(f"  p99: {percentile(latencies, 99):.1f}s")
        print(f"  avg: {statistics.mean(latencies):.1f}s")

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

    # Key insight
    selector_errors = failure_types.get("selector_error", 0)
    print(f"\nKey Insight:")
    if selector_errors == 0:
        print(f"  Selector errors: 0 — Locator strategy is working!")
    else:
        print(f"  Selector errors: {selector_errors} — Locators need updating")

    print(f"\nResults:     {results_file}")
    print(f"Screenshots: {SCREENSHOTS_DIR}")
    print(f"HTML dumps:  {HTML_DIR}")


def _save_results(path: Path, results: list, latencies: list, start_time: float):
    """Save results to JSON with full metrics."""
    successes = sum(1 for r in results if r["success"])
    total = len(results)

    failure_types = {}
    for r in results:
        if not r["success"]:
            ft = r.get("failure_type", "unknown")
            failure_types[ft] = failure_types.get(ft, 0) + 1

    latency_stats = {}
    if latencies:
        latency_stats = {
            "p50": round(percentile(latencies, 50), 1),
            "p95": round(percentile(latencies, 95), 1),
            "p99": round(percentile(latencies, 99), 1),
            "avg": round(statistics.mean(latencies), 1),
        }

    data = {
        "summary": {
            "total": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": round(successes / total, 4) if total > 0 else 0,
            "elapsed_hours": round((time.monotonic() - start_time) / 3600, 2),
            "latency_ms": latency_stats,
            "failure_breakdown": failure_types,
        },
        "results": results,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    asyncio.run(run_reliability_test(hours, interval))
