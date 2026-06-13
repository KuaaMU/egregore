"""Benchmark cases — real questions to test collective intelligence.

These are NOT synthetic test cases. They are real questions
where we expect synthesis to produce better answers than
any individual model.

Each case has:
- A question
- A domain
- Success criteria (what makes a good answer)

The evaluator will:
1. Ask each model
2. Synthesize
3. Score everything
4. Compare synthesis vs best individual
"""

from egregore.domain.benchmark.models import Domain

# Each case is (question, domain, success_criteria)
BENCHMARK_CASES: list[tuple[str, Domain, str]] = [
    # === Software Engineering ===
    (
        "Should I use Rust or Go for a high-performance CLI tool that processes large log files? "
        "The team has 3 junior developers and 1 senior. Time to market matters.",
        Domain.SOFTWARE,
        "Considers team skill, performance needs, time constraints. Gives specific recommendation with reasoning.",
    ),
    (
        "I'm building a real-time collaborative editor like Google Docs. "
        "What architecture should I use? Consider conflict resolution, scalability, and offline support.",
        Domain.ARCHITECTURE,
        "Addresses CRDTs vs OT, WebSocket architecture, offline sync. Considers tradeoffs, not just one approach.",
    ),
    (
        "My PostgreSQL query takes 30 seconds on a table with 100M rows. "
        "The query joins 4 tables with WHERE clauses on 2 columns. What should I do?",
        Domain.SOFTWARE,
        "Covers indexing strategy, query optimization, EXPLAIN ANALYZE, partitioning, and when to denormalize.",
    ),

    # === Architecture ===
    (
        "How should a startup with 10 engineers organize their monorepo vs polyrepo? "
        "They use TypeScript frontend, Python backend, and have 2 ML engineers.",
        Domain.ARCHITECTURE,
        "Considers team size, language boundaries, CI/CD complexity, and practical tradeoffs.",
    ),
    (
        "Design a rate limiting system for an API that serves 100K requests/second. "
        "It needs to support per-user, per-endpoint, and global limits.",
        Domain.ARCHITECTURE,
        "Covers algorithms (token bucket, sliding window), distributed coordination, Redis vs local.",
    ),

    # === Research ===
    (
        "What are the most promising approaches to reducing hallucinations in LLMs? "
        "Compare RAG, fine-tuning, constitutional AI, and chain-of-thought verification.",
        Domain.RESEARCH,
        "Covers multiple approaches with tradeoffs. Not just listing, but comparing effectiveness.",
    ),
    (
        "How does mixture of experts (MoE) work in modern LLMs? "
        "Explain the routing mechanism, training challenges, and inference efficiency.",
        Domain.RESEARCH,
        "Technical accuracy, covers gating networks, load balancing, expert specialization.",
    ),

    # === Philosophy ===
    (
        "If an AI system passes the Turing test but has no subjective experience, "
        "is it intelligent? What frameworks help us think about this?",
        Domain.PHILOSOPHY,
        "Engages with multiple philosophical positions (functionalism, phenomenology, behaviorism). Not superficial.",
    ),

    # === Startup ===
    (
        "I'm building an open-source developer tool. "
        "What's the best monetization strategy? Compare hosted vs enterprise vs marketplace.",
        Domain.STARTUP,
        "Covers multiple models with real examples. Considers developer community dynamics.",
    ),
    (
        "What is the moat of an AI wrapper startup? "
        "If the underlying models improve, does the wrapper become worthless?",
        Domain.STARTUP,
        "Engages with the real question: where is durable value in the AI stack?",
    ),

    # === Math ===
    (
        "Explain why the Riemann Hypothesis matters for number theory. "
        "What would change if it were proven true vs false?",
        Domain.MATH,
        "Connects RH to prime distribution, zeta function, and practical implications. Not just Wikipedia.",
    ),

    # === Creative ===
    (
        "Write a compelling pitch for a documentary about the history of "
        "collective intelligence, from ant colonies to AI systems.",
        Domain.CREATIVE,
        "Engaging narrative, unexpected connections, clear structure, emotional resonance.",
    ),
]


def get_cases_by_domain(domain: Domain) -> list[tuple[str, Domain, str]]:
    """Get benchmark cases for a specific domain."""
    return [(q, d, c) for q, d, c in BENCHMARK_CASES if d == domain]


def get_all_domains() -> list[Domain]:
    """Get all domains represented in benchmark cases."""
    return list(set(d for _, d, _ in BENCHMARK_CASES))
