from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.artifacts import ArtifactStore
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import Brief, NodeOutcome, WavePlan
from wolves.graph.master import admit


def _brief(node_id: str, *, kind: str = "research", artifact_ids: list[str] | None = None) -> Brief:
    return Brief(node_id=node_id, kind=kind, objective=node_id, brief="...", input_artifact_ids=artifact_ids or [])


def test_admission_trims_invalid_and_over_cap_briefs(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, graph_max_nodes=10, graph_max_wave_workers=3)
    store = ArtifactStore(tmp_path / "artifacts")
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    known = store.add(kind="evidence", created_by="research-0", summary="s", payload={"summary": "s"})
    done = _brief("research-0")
    board.merge([done], [NodeOutcome(node_id="research-0", kind="research", ok=True, artifact_ids=[known.id])])

    plan = WavePlan(
        briefs=[
            _brief("research-0"),
            _brief("quant-1", kind="quant", artifact_ids=[known.id]),
            _brief("research-2", artifact_ids=["evidence-deadbeef"]),
            _brief("forecast-a", kind="forecast"),
            _brief("forecast-b", kind="forecast"),
            _brief("research-3"),
            _brief("research-4"),
        ]
    )

    admitted = admit(plan, board=board, settings=settings)

    assert [b.node_id for b in admitted] == ["quant-1", "forecast-a", "research-3"]
    deps.runtime.shutdown()


def test_admission_respects_remaining_node_budget(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, graph_max_nodes=2, graph_max_wave_workers=4)
    store = ArtifactStore(tmp_path / "artifacts")
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    done = _brief("research-0")
    board.merge([done], [NodeOutcome(node_id="research-0", kind="research", ok=True)])

    plan = WavePlan(briefs=[_brief("research-1"), _brief("research-2")])

    assert [b.node_id for b in admit(plan, board=board, settings=settings)] == ["research-1"]
    deps.runtime.shutdown()
