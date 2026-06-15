from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.article_cache import ArticleCache
from wolves.agent.relevance_memory import RelevanceMemory
from wolves.agent.source_memory import SourceMemory
from wolves.agent.tools.retrieval.rank_relevance import Candidate, RankRelevanceArgs, _rank_relevance
from wolves.run_agent import _source_relevance


async def test_ranking_records_artifact_memory_and_tiers(tmp_path: Path):
    rankings = {
        "rankings": [
            {"url": "https://www.reuters.com/a", "score": 0.9, "reason": "official confirmation"},
            {"url": "https://www.goal.com/b", "score": 0.2, "reason": "aggregator speculation"},
        ]
    }
    memory = SourceMemory(tmp_path / "agent-state" / "sources_seen.jsonl")
    memory.record("https://www.goal.com/b", run_id="agent-yesterday", disposition="fetched")
    relevance = RelevanceMemory(tmp_path / "agent-state" / "relevance_memory.jsonl")
    deps = dataclasses.replace(
        build_graph_deps(tmp_path, structured=[rankings]),
        artifacts=build_run_store(tmp_path),
        source_memory=memory,
        relevance_memory=relevance,
        actor="research-keeper",
    )

    args = RankRelevanceArgs(
        sub_question="is the keeper fit for Thursday",
        candidates=[
            Candidate(url="https://www.reuters.com/a", title="Keeper trains fully"),
            Candidate(url="https://www.goal.com/b", title="Keeper doubt rumours"),
        ],
    )
    with deps.runtime.run_trace():
        result = await _rank_relevance(args, deps)

    assert result.ok
    assert result.payload is not None
    top, second = result.payload["rankings"]
    assert top["url"] == "https://www.reuters.com/a"
    assert top["tier"] == 1 and top["score"] == 0.9
    assert second["tier"] == 3
    assert second["seen_in_run"] == "agent-yesterday"

    assert deps.artifacts is not None
    [record] = [r for r in deps.artifacts.all() if r.kind == "retrieval"]
    artifact = deps.artifacts.get(record.id)
    assert artifact is not None
    assert artifact.payload["sub_question"].startswith("is the keeper fit")

    assert memory.seen("https://www.reuters.com/a") is not None
    prior = relevance.latest("https://www.goal.com/b")
    assert prior is not None and prior.score == 0.2 and prior.ranked_at
    deps.runtime.shutdown()


async def test_ranking_failure_degrades_to_judgement(tmp_path: Path):
    deps = dataclasses.replace(build_graph_deps(tmp_path, structured=[]), actor="research-1")
    args = RankRelevanceArgs(sub_question="q", candidates=[Candidate(url="https://example.com/x", title="t")])
    result = await _rank_relevance(args, deps)
    assert not result.ok
    assert result.error is not None and result.error.type == "ranking_unavailable"
    deps.runtime.shutdown()


def test_snapshot_sources_merge_ranked_fetched_and_cited_urls(tmp_path: Path):
    store = build_run_store(tmp_path)
    memory = SourceMemory(tmp_path / "agent-state" / "sources_seen.jsonl")
    articles = ArticleCache(tmp_path / "agent-state" / "articles")
    deps = dataclasses.replace(
        build_graph_deps(tmp_path),
        artifacts=store,
        source_memory=memory,
        articles=articles,
    )

    ranked_url = "https://www.reuters.com/sports/soccer/keeper-fit"
    cited_url = "https://www.thefa.com/news/2026/jun/14/england-squad"
    fetched_url = "https://www.bbc.co.uk/sport/football/fetched-only"
    redirect_url = "https://short.example/england"
    final_url = "https://www.reuters.com/sports/soccer/england-squad"
    memory.record(ranked_url, run_id=deps.runtime.run_id, disposition="fetched")
    memory.record(fetched_url, run_id=deps.runtime.run_id, disposition="fetched")
    memory.record(redirect_url, run_id=deps.runtime.run_id, disposition="fetched")
    memory.record(final_url, run_id=deps.runtime.run_id, disposition="fetched")
    assert {r.url for r in memory.seen_in_run(deps.runtime.run_id)} == {
        ranked_url,
        fetched_url,
        redirect_url,
        final_url,
    }
    articles.put(
        url=cited_url,
        final_url=cited_url,
        title="England squad update",
        text="Bukayo Saka trained fully.",
        run_id=deps.runtime.run_id,
    )
    articles.put(
        url=fetched_url,
        final_url=fetched_url,
        title="Fetched page",
        text="Read but not used.",
        run_id=deps.runtime.run_id,
    )
    articles.put(
        url=redirect_url,
        final_url=final_url,
        title="England squad from wire",
        text="Wire copy with a redirect.",
        run_id=deps.runtime.run_id,
    )
    store.add(
        kind="retrieval",
        created_by="research-availability",
        summary="ranked availability sources",
        payload={
            "sub_question": "which England attackers are available",
            "rankings": [
                {
                    "url": ranked_url,
                    "title": "Keeper trains fully",
                    "tier": 1,
                    "score": 0.91,
                    "reason": "syndicated match-camp reporting",
                    "seen_in_run": None,
                },
                {
                    "url": redirect_url,
                    "title": "England squad latest",
                    "tier": 1,
                    "score": 0.82,
                    "reason": "wire squad availability note",
                    "seen_in_run": None,
                },
                {
                    "url": "https://bad.example/nope",
                    "title": "Bad number",
                    "tier": 9,
                    "score": "nan",
                    "reason": "malformed",
                    "seen_in_run": None,
                },
            ],
        },
    )
    deps.ledger.append(
        claim="Saka trained fully with England",
        source_url=cited_url,
        status="confirmed",
        mechanism="availability",
        team_id="england",
        relevance=0.8,
    )
    deps.ledger.append(
        claim="Same source, lower relevance",
        source_url=cited_url,
        status="probable",
        mechanism="availability",
        team_id="england",
        relevance=0.2,
    )
    deps.ledger.append(
        claim="England squad wire copy confirmed",
        source_url=final_url,
        status="confirmed",
        mechanism="availability",
        team_id="england",
        relevance=0.7,
    )

    sources = _source_relevance(deps)
    by_url = {source.url: source for source in sources}

    assert by_url[cited_url].cited is True
    assert by_url[cited_url].fetched is False
    assert by_url[cited_url].ranked is False
    assert by_url[cited_url].score == 0.8
    assert by_url[cited_url].hostname == "www.thefa.com"
    assert by_url[ranked_url].cited is False
    assert by_url[ranked_url].fetched is True
    assert by_url[ranked_url].ranked is True
    assert by_url[ranked_url].sub_question == "which England attackers are available"
    assert by_url[ranked_url].retrieval_id == "retrieval-001"
    assert by_url[ranked_url].created_by == "research-availability"
    assert by_url[fetched_url].cited is False
    assert by_url[fetched_url].ranked is False
    assert by_url[fetched_url].fetched is True
    assert by_url[fetched_url].reason == "fetched this run"
    assert redirect_url not in by_url
    assert by_url[final_url].cited is True
    assert by_url[final_url].ranked is True
    assert by_url[final_url].fetched is True
    assert by_url[final_url].score == 0.82
    assert by_url["https://bad.example/nope"].score is None
    assert by_url["https://bad.example/nope"].tier is None
    deps.runtime.shutdown()
