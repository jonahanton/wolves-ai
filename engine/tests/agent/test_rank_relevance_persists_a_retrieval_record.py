from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.source_memory import SourceMemory
from wolves.agent.tools.retrieval.rank_relevance import Candidate, RankRelevanceArgs, _rank_relevance


async def test_ranking_records_artifact_memory_and_tiers(tmp_path: Path):
    rankings = {
        "rankings": [
            {"url": "https://www.reuters.com/a", "score": 0.9, "reason": "official confirmation"},
            {"url": "https://www.goal.com/b", "score": 0.2, "reason": "aggregator speculation"},
        ]
    }
    memory = SourceMemory(tmp_path / "agent-state" / "sources_seen.jsonl")
    memory.record("https://www.goal.com/b", run_id="agent-yesterday", disposition="fetched")
    deps = dataclasses.replace(
        build_graph_deps(tmp_path, structured=[rankings]),
        artifacts=build_run_store(tmp_path),
        source_memory=memory,
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
    deps.runtime.shutdown()


async def test_ranking_failure_degrades_to_judgement(tmp_path: Path):
    deps = dataclasses.replace(build_graph_deps(tmp_path, structured=[]), actor="research-1")
    args = RankRelevanceArgs(sub_question="q", candidates=[Candidate(url="https://example.com/x", title="t")])
    result = await _rank_relevance(args, deps)
    assert not result.ok
    assert result.error is not None and result.error.type == "ranking_unavailable"
    deps.runtime.shutdown()
