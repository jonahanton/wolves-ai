from __future__ import annotations

import json
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.graph.artifacts import NodeArtifactStore
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import Brief, NodeOutcome

SENTINEL = "SECRET-PAYLOAD-TEXT-THAT-MUST-NOT-LEAK"


def test_summary_is_metadata_only(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = NodeArtifactStore(tmp_path / "artifacts")
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)

    artifact = store.add(
        kind="quant",
        created_by="quant-delta",
        summary="A 15 Elo delta lifts champion prob by 0.4pp. " + "x" * 200,
        payload={"summary": "delta check", "findings": [SENTINEL], "headline_value": 0.004},
    )
    brief = Brief(node_id="quant-delta", kind="quant", objective="Delta sensitivity " + "y" * 100, brief="...")
    board.merge([brief], [NodeOutcome(node_id="quant-delta", kind="quant", ok=True, artifact_ids=[artifact.id])])

    state = json.loads(board.summary())

    assert SENTINEL not in board.summary()
    assert state["wave"] == 1
    assert "llm_calls" in state["budget"]
    [node] = state["nodes"]
    assert node["node_id"] == "quant-delta"
    assert len(node["objective"]) == 80
    [meta] = state["artifacts"]
    assert meta["id"] == artifact.id
    assert meta["by"] == "quant-delta"
    assert len(meta["summary"]) == 100
    deps.runtime.shutdown()
