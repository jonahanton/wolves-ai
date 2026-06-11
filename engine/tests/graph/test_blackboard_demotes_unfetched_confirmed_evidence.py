from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.source_memory import SourceMemory
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import LedgerEvidence, NodeOutcome, NodePatch, ResearchOutput


def _evidence(claim: str, url: str) -> LedgerEvidence:
    return LedgerEvidence(claim=claim, source_url=url, status="confirmed", team_id="england")


def test_confirmed_needs_a_page_fetched_this_run(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    memory.record("https://www.reuters.com/fetched", run_id=deps.runtime.run_id, disposition="fetched")
    memory.record("https://www.bbc.co.uk/stale", run_id="some-earlier-run", disposition="fetched")
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime, source_memory=memory)

    output = ResearchOutput(
        summary="three confirmed claims of unequal provenance",
        evidence=[
            _evidence("backed by a fetched page", "https://www.reuters.com/fetched"),
            _evidence("backed only by a snippet", "https://www.bbc.co.uk/stale"),
            _evidence("internal tool output", "internal://odds/consensus"),
            _evidence("first-party odds tool output", "https://tools.internal/get_odds"),
        ],
    )
    artifact = store.add(kind="evidence", created_by="research-1", summary=output.summary, payload=output.model_dump())
    brief = NodePatch(node_id="research-1", kind="research", objective="news", brief="...")

    board.merge([brief], [NodeOutcome(node_id="research-1", kind="research", ok=True, artifact_ids=[artifact.id])])

    statuses = {e.claim: e.status for e in deps.ledger.all()}
    assert statuses["backed by a fetched page"] == "confirmed"
    assert statuses["backed only by a snippet"] == "probable"
    assert statuses["internal tool output"] == "confirmed"
    assert statuses["first-party odds tool output"] == "confirmed"

    amended = {e["claim"]: e["status"] for e in store.get(artifact.id).payload["evidence"]}
    assert amended["backed only by a snippet"] == "probable"
    assert amended["backed by a fetched page"] == "confirmed"
    deps.runtime.shutdown()
