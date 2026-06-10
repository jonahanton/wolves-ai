from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.config import Settings
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import GraphPatch, NodeOutcome, NodePatch
from wolves.graph.master import admit


def _brief(node_id: str, *, kind: str = "research", artifact_ids: list[str] | None = None) -> NodePatch:
    return NodePatch(node_id=node_id, kind=kind, objective=node_id, brief="...", input_artifact_ids=artifact_ids or [])


def test_admission_trims_invalid_and_over_cap_briefs(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, graph_max_nodes=10, graph_max_wave_workers=3)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    known = store.add(kind="evidence", created_by="research-0", summary="s", payload={"summary": "s"})
    done = _brief("research-0")
    board.merge([done], [NodeOutcome(node_id="research-0", kind="research", ok=True, artifact_ids=[known.id])])

    plan = GraphPatch(
        ops=[
            _brief("research-0"),
            _brief("quant-1", kind="quant", artifact_ids=[known.id]),
            _brief("research-2", artifact_ids=["evidence-deadbeef"]),
            _brief("forecast-a", kind="forecast"),
            _brief("forecast-b", kind="forecast"),
            _brief("research-3"),
            _brief("research-4"),
        ]
    )

    admitted, dropped = admit(plan, board=board, settings=settings)

    assert [b.node_id for b in admitted] == ["quant-1", "forecast-a", "research-3"]
    assert [d.split(":")[0] for d in dropped] == ["research-0", "research-2", "forecast-b", "research-4"]
    deps.runtime.shutdown()


def test_admission_respects_remaining_node_budget(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, graph_max_nodes=2, graph_max_wave_workers=4)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    done = _brief("research-0")
    board.merge([done], [NodeOutcome(node_id="research-0", kind="research", ok=True)])

    plan = GraphPatch(ops=[_brief("research-1"), _brief("research-2")])

    assert [b.node_id for b in admit(plan, board=board, settings=settings)[0]] == ["research-1"]
    deps.runtime.shutdown()
