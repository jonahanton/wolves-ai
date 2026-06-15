from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_run_store
from wolves.config import Settings
from wolves.graph.agents import _NODE_SPECS
from wolves.graph.contracts import Brief
from wolves.graph.nodes import _kickoff


def test_research_nodes_keep_request_budget_for_retrieval(tmp_path: Path):
    names = {spec.name for spec in _NODE_SPECS["research"]}

    assert "think" not in names
    assert "todo_write" not in names
    assert "read_artifact" in names

    kickoff = _kickoff(
        Brief(node_id="research-news", kind="research", objective="Check news", brief="Find changed facts."),
        build_run_store(tmp_path),
        settings=Settings(_env_file=None, runs_root=tmp_path, storage_mode="local"),
    )

    assert "read_artifact is free and does not count" in kickoff
    assert "think" not in kickoff
    assert "todo_write" not in kickoff
