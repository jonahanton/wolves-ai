from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import LedgerEvidence, NodeOutcome, NodePatch, ResearchOutput


def _merge(board, store, node_id: str, evidence: list[LedgerEvidence]) -> None:
    output = ResearchOutput(summary="sweep", evidence=evidence)
    artifact = store.add(kind="evidence", created_by=node_id, summary="sweep", payload=output.model_dump())
    brief = NodePatch(node_id=node_id, kind="research", objective="news", brief="...")
    board.merge([brief], [NodeOutcome(node_id=node_id, kind="research", ok=True, artifact_ids=[artifact.id])])


def test_identical_claim_and_url_from_a_later_node_is_not_re_appended(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    saka = LedgerEvidence(
        claim="Saka still recovering", source_url="https://www.reuters.com/saka", status="probable", team_id="england"
    )
    fresh = LedgerEvidence(
        claim="Eze confirmed at No.10", source_url="https://www.thefa.com/eze", status="probable", team_id="england"
    )

    _merge(board, store, "research-1", [saka])
    _merge(board, store, "research-2", [saka, fresh])

    claims = [e.claim for e in deps.ledger.all()]
    assert claims == ["Saka still recovering", "Eze confirmed at No.10"]
    deps.runtime.shutdown()
