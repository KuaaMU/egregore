"""Provider Metrics — tracks reliability data per provider.

GPT's insight: Metrics are more real than State.
Track what actually happens, not what we think should happen.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderMetrics:
    """Reliability metrics for a provider."""

    provider_name: str = ""
    requests: int = 0
    successes: int = 0
    failures: int = 0
    latencies: list[float] = field(default_factory=list)
    failure_types: dict[str, int] = field(default_factory=dict)
    last_failure: str = ""

    def record_success(self, latency_ms: float) -> None:
        self.requests += 1
        self.successes += 1
        self.latencies.append(latency_ms)

    def record_failure(self, failure_type: str, error: str = "") -> None:
        self.requests += 1
        self.failures += 1
        self.failure_types[failure_type] = self.failure_types.get(failure_type, 0) + 1
        self.last_failure = error

    @property
    def success_rate(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.successes / self.requests

    def _percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        k = (len(s) - 1) * (p / 100)
        f = int(k)
        c = f + 1
        if c >= len(s):
            return s[-1]
        return s[f] + (k - f) * (s[c] - s[f])

    @property
    def p50(self) -> float:
        return self._percentile(50)

    @property
    def p95(self) -> float:
        return self._percentile(95)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    def summary(self) -> str:
        return (
            f"{self.provider_name}: "
            f"{self.success_rate:.0%} ({self.successes}/{self.requests}), "
            f"p50={self.p50:.0f}ms, p95={self.p95:.0f}ms"
        )
