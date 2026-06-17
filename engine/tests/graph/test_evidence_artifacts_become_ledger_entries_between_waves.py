from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import CandidateBranch, LedgerEvidence, NodeOutcome, NodePatch, ResearchOutput


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


def test_merge_resolves_branch_evidence_indices_to_ledger_ids(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)

    output = ResearchOutput(
        summary="France branch found.",
        evidence=[
            LedgerEvidence(
                claim="France forward returned to full training",
                source_url="https://www.reuters.com/france",
                status="confirmed",
                mechanism="availability",
                proposed_delta=0.05,
                team_id="france",
            )
        ],
        candidate_branches=[
            CandidateBranch(
                branch_id="france-attack-fit",
                teams=["france"],
                hypothesis="France's attack may be closer to full strength than the model assumes.",
                support="Evidence item 1 says the forward returned to full training.",
                collapse_condition="Collapse if quant finds the title effect below the floor.",
                evidence_indices=[1],
                confidence="medium",
                suggested_quant_question="Price France with the forward available.",
            )
        ],
    )
    artifact = store.add(kind="evidence", created_by="research-1", summary=output.summary, payload=output.model_dump())
    brief = NodePatch(node_id="research-1", kind="research", objective="france news", brief="...")

    board.merge([brief], [NodeOutcome(node_id="research-1", kind="research", ok=True, artifact_ids=[artifact.id])])

    amended = store.get(artifact.id)
    assert amended is not None
    [branch] = amended.payload["candidate_branches"]
    assert branch["source_ids"] == ["led-0001"]
    deps.runtime.shutdown()
