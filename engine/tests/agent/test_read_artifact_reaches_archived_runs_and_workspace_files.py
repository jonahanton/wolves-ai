from __future__ import annotations

from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.tools.meta.read_artifact import ReadArtifactArgs, _read_artifact
from wolves.graph.artifacts import RunArtifactStore
from wolves.s3.artifacts import ArtifactStore


@pytest.fixture
def deps(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    old = RunArtifactStore(ArtifactStore(deps.settings), run_id="agent-old")
    workspace = tmp_path / "runs" / "agent-old" / "workspace" / "quant" / "quant-1"
    workspace.mkdir(parents=True)
    (workspace / "analysis_001.py").write_text("result = {'gap': 1.2}", encoding="utf-8")
    old.add(
        kind="quant",
        created_by="quant-1",
        summary="old gap analysis",
        payload={"findings": ["gap 1.2pp"]},
        workspace_prefix="runs/agent-old/workspace/quant/quant-1",
    )
    deps.artifacts = build_run_store(tmp_path)
    yield deps
    deps.runtime.shutdown()


async def test_archived_artifact_and_script_readable_by_run_id(deps):
    result = await _read_artifact(ReadArtifactArgs(artifact_id="quant-001", run_id="agent-old"), deps)
    assert result.ok
    assert result.payload["payload"]["findings"] == ["gap 1.2pp"]
    assert result.payload["workspace_files"] == ["analysis_001.py"]

    scripted = await _read_artifact(
        ReadArtifactArgs(artifact_id="quant-001", run_id="agent-old", file="analysis_001.py"), deps
    )
    assert scripted.payload["file"]["content"] == "result = {'gap': 1.2}"


async def test_workspace_escape_refused(deps):
    result = await _read_artifact(
        ReadArtifactArgs(artifact_id="quant-001", run_id="agent-old", file="../../../ledger.jsonl"), deps
    )
    assert not result.ok
    assert result.error.type == "bad_path"
