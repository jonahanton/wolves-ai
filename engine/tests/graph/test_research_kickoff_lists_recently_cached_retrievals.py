from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.agent.article_cache import ArticleCache
from wolves.agent.relevance_memory import RelevanceMemory
from wolves.graph.nodes import _retrievals_digest


def test_digest_carries_age_and_prior_judgement(tmp_path: Path):
    cache = ArticleCache(tmp_path / "agent-state" / "articles")
    cache.put(
        url="https://www.bbc.co.uk/squad",
        final_url="https://www.bbc.co.uk/squad",
        title="Squad named",
        text="x" * 200,
        run_id="agent-yesterday",
    )
    relevance = RelevanceMemory(tmp_path / "agent-state" / "relevance_memory.jsonl")
    relevance.record(
        url="https://www.bbc.co.uk/squad",
        sub_question="squad news",
        score=0.85,
        reason="official squad list",
        run_id="agent-yesterday",
    )
    deps = dataclasses.replace(build_graph_deps(tmp_path), articles=cache, relevance_memory=relevance)

    digest = _retrievals_digest(deps)

    assert "Squad named" in digest and "0h ago" in digest
    assert "judged 0.85: official squad list" in digest
    deps.runtime.shutdown()


def test_digest_empty_without_cache_or_recent_articles(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    assert _retrievals_digest(deps) == ""
    cached = dataclasses.replace(deps, articles=ArticleCache(tmp_path / "agent-state" / "articles"))
    assert _retrievals_digest(cached) == ""
    deps.runtime.shutdown()
