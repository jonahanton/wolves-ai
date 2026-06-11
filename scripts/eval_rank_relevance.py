"""Score rank_relevance against the labelled fixtures using the live model (costs cents).

Usage: STORAGE_MODE=local uv run --project engine python scripts/eval_rank_relevance.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FIXTURES = Path(__file__).resolve().parents[1] / "engine/tests/agent/fixtures/rank_relevance_eval.json"


def spearman(labelled_order: list[str], scores: dict[str, float]) -> float:
    n = len(labelled_order)
    if n < 2:
        return 1.0
    labelled_rank = {url: i for i, url in enumerate(labelled_order)}
    model_rank = {url: i for i, url in enumerate(sorted(labelled_order, key=lambda u: -scores[u]))}
    d2 = sum((labelled_rank[u] - model_rank[u]) ** 2 for u in labelled_order)
    return 1.0 - 6.0 * d2 / (n * (n**2 - 1))


def score_case(case: dict[str, Any], rankings: list[dict[str, Any]]) -> str | None:
    """One line of metrics, or None when a labelled candidate went unscored."""
    scores = {r["url"]: r["score"] for r in rankings if r["score"] is not None}
    labelled = [url for bucket in case["expected_buckets"] for url in bucket]
    if any(url not in scores for url in labelled):
        return None
    useful = {url for bucket in case["expected_buckets"][:2] for url in bucket}
    top3 = [r["url"] for r in rankings[:3]]
    rho = spearman(labelled, scores)
    precision = sum(url in useful for url in top3) / 3
    return f"rho={rho:+.2f} top3={precision:.2f}  {case['sub_question'][:70]}"


async def evaluate() -> int:
    from wolves.agent.tools.retrieval.rank_relevance import Candidate, RankRelevanceArgs, _rank_relevance
    from wolves.config import Settings
    from wolves.llm.anthropic import build_llm
    from wolves.llm.observed import ObservedLLM
    from wolves.observability import Caps, InMemoryTracer, build_runtime

    settings = Settings()
    runtime = build_runtime(
        run_id="rank-relevance-eval", tracer=InMemoryTracer(), caps=Caps(), runs_root=settings.runs_root
    )
    llm = build_llm(settings, model=settings.worker_model)
    # The tool only reaches llm, memory, artifacts, actor and as_of; a full
    # AgentDeps would drag in every client for nothing.
    deps = SimpleNamespace(
        llm=ObservedLLM(llm, runtime), source_memory=None, artifacts=None, actor="eval", as_of="", runtime=runtime
    )

    failures = 0
    try:
        for case in json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]:
            deps.as_of = case["as_of"]
            args = RankRelevanceArgs(
                sub_question=case["sub_question"],
                candidates=[Candidate(**c) for c in case["candidates"]],
            )
            with runtime.observe(kind="tool", actor="eval", name="rank_relevance_eval"):
                result = await _rank_relevance(args, deps)
            line = score_case(case, result.payload["rankings"]) if result.ok else None
            if line is None:
                failures += 1
                print(f"FAIL {case['sub_question'][:60]}: {result.error if not result.ok else 'unscored candidates'}")
                continue
            print(line)
            for r in result.payload["rankings"]:
                print(f"    {r['score']:.2f} t{r['tier'] or '-'} {r['url'][:78]}\n         {r['reason'][:100]}")
    finally:
        await llm.aclose()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(evaluate()))
