from __future__ import annotations

import json
from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import NodeOutcome, NodePatch

SENTINEL = "SECRET-PAYLOAD-TEXT-THAT-MUST-NOT-LEAK"


def test_summary_is_metadata_only(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)

    artifact = store.add(
        kind="quant",
        created_by="quant-delta",
        summary="A 15 Elo delta lifts champion prob by 0.4pp. " + "x" * 200,
        payload={"summary": "delta check", "findings": [SENTINEL], "headline_value": 0.004},
    )
    brief = NodePatch(node_id="quant-delta", kind="quant", objective="Delta sensitivity " + "y" * 100, brief="...")
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


def test_summary_repeats_run_context_between_waves(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    board = Blackboard(
        artifacts=store,
        ledger=deps.ledger,
        runtime=deps.runtime,
        run_context={"continuity_anchor": "Previous agent forecast agent-yesterday. This is not a first run."},
    )

    state = json.loads(board.summary())

    assert state["run_context"]["continuity_anchor"] == (
        "Previous agent forecast agent-yesterday. This is not a first run."
    )
    deps.runtime.shutdown()


def test_summary_surfaces_referee_critique_challenges(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    store.add(
        kind="critique",
        created_by="referee",
        summary="France gap needs quant audit",
        payload={
            "challenges": [
                "master: France market gap needs a quant audit. Next: open a quant follow-up."
            ],
            "suggested_master_brief": "Open a quant node to test the France market premium.",
            "secret": SENTINEL,
        },
    )

    state = json.loads(board.summary())

    assert state["open_challenges"] == [
        "master: France market gap needs a quant audit. Next: open a quant follow-up.",
        "Open a quant node to test the France market premium.",
    ]
    assert SENTINEL not in board.summary()
    deps.runtime.shutdown()
