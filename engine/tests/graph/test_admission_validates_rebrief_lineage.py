from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.config import Settings
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import GraphPatch, NodeOutcome, NodePatch
from wolves.graph.master import admit


def _patch(node_id: str, *, kind: str = "research", replaces: str | None = None) -> NodePatch:
    return NodePatch(node_id=node_id, kind=kind, objective=node_id, brief="...", replaces=replaces)


def test_rebrief_lineage_rules(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local")
    board = Blackboard(artifacts=build_run_store(tmp_path), ledger=deps.ledger, runtime=deps.runtime)
    failed = _patch("research-news")
    board.merge([failed], [NodeOutcome(node_id="research-news", kind="research", ok=False, error="boom")])

    first = GraphPatch(ops=[_patch("research-news-2", replaces="research-news")])
    admitted, dropped = admit(first, board=board, settings=settings)
    assert [op.node_id for op in admitted] == ["research-news-2"]
    assert dropped == []
    board.merge(admitted, [NodeOutcome(node_id="research-news-2", kind="research", ok=True)])
    assert board.nodes[0].replaced_by == "research-news-2"

    second = GraphPatch(
        ops=[
            _patch("research-news-3", replaces="research-news"),
            _patch("research-news-4", replaces="research-never-existed"),
        ]
    )
    admitted, dropped = admit(second, board=board, settings=settings)
    assert admitted == []
    assert "already superseded" in dropped[0]
    assert "unknown node" in dropped[1]
    deps.runtime.shutdown()


def test_per_kind_node_budgets(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local", graph_max_critic_nodes=1, graph_max_wave_workers=4)
    board = Blackboard(artifacts=build_run_store(tmp_path), ledger=deps.ledger, runtime=deps.runtime)
    board.merge(
        [_patch("critic-1", kind="critic")],
        [NodeOutcome(node_id="critic-1", kind="critic", ok=True)],
    )

    patch = GraphPatch(ops=[_patch("critic-2", kind="critic"), _patch("research-1")])
    admitted, dropped = admit(patch, board=board, settings=settings)

    assert [op.node_id for op in admitted] == ["research-1"]
    assert "critic node budget" in dropped[0]
    deps.runtime.shutdown()
