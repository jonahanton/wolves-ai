from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_run_store
from wolves.config import Settings
from wolves.graph.agents import _NODE_SPECS
from wolves.graph.contracts import Brief
from wolves.graph.nodes import _kickoff


def test_worker_nodes_keep_request_budget_for_real_tools(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    store = build_run_store(tmp_path)

    for kind in ("research", "quant", "forecast", "critic"):
        names = {spec.name for spec in _NODE_SPECS[kind]}

        assert "think" not in names
        assert "todo_write" not in names
        assert "read_artifact" in names

        kickoff = _kickoff(
            Brief(node_id=f"{kind}-news", kind=kind, objective="Check news", brief="Find changed facts."),
            store,
            settings=settings,
        )

        assert "read_artifact is free and does not count" in kickoff
        assert "think" not in kickoff
        assert "todo_write" not in kickoff
