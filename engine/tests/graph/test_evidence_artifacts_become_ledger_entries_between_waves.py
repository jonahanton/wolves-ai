from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import LedgerEvidence, NodeOutcome, NodePatch, ResearchOutput


def test_merge_converts_evidence_serially(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)

    output = ResearchOutput(
        summary="keeper fit, striker doubtful",
        evidence=[
            LedgerEvidence(
                claim="Keeper confirmed fit",
                source_url="https://www.reuters.com/a",
                status="confirmed",
                mechanism="keeper returns",
                proposed_delta=0.15,
                team_id="england",
            ),
            LedgerEvidence(
                claim="Striker doubtful per local press",
                source_url="https://example.com/b",
                status="rumour",
                team_id="england",
            ),
        ],
    )
    artifact = store.add(kind="evidence", created_by="research-1", summary=output.summary, payload=output.model_dump())
    brief = NodePatch(node_id="research-1", kind="research", objective="squad news", brief="...")

    board.merge([brief], [NodeOutcome(node_id="research-1", kind="research", ok=True, artifact_ids=[artifact.id])])

    entries = deps.ledger.all()
    assert [e.id for e in entries] == ["led-0001", "led-0002"]
    assert entries[0].status == "confirmed"
    assert entries[0].proposed_delta == 0.15
    assert entries[1].status == "rumour"
    deps.runtime.shutdown()
