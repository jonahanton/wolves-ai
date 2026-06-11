from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.graph.conftest import build_run_store
from wolves.config import Settings
from wolves.graph.artifacts import MissingRunIndexError, ReadOnlyRunError, RunArtifactStore
from wolves.s3.artifacts import ArtifactStore


def test_roundtrip_with_sequential_ids(tmp_path: Path):
    store = build_run_store(tmp_path)
    payload = {"summary": "keeper fit", "evidence": [{"claim": "trained in full"}]}

    artifact = store.add(kind="evidence", created_by="research-keeper", summary="keeper fit", payload=payload)
    second = store.add(kind="evidence", created_by="research-keeper", summary="more", payload={})
    quant = store.add(kind="quant", created_by="quant-1", summary="q", payload={})

    assert artifact.id == "evidence-001"
    assert second.id == "evidence-002"
    assert quant.id == "quant-001"
    assert store.has(artifact.id)
    fetched = store.get(artifact.id)
    assert fetched is not None
    assert fetched.payload == payload
    assert fetched.created_by == "research-keeper"

    on_disk = json.loads(
        (tmp_path / "runs" / "graph-run" / "artifacts" / "evidence-001.json").read_text(encoding="utf-8")
    )
    assert on_disk["payload"] == payload

    assert store.get("evidence-999") is None
    assert not store.has("evidence-999")


def test_cross_run_open_reads_index_and_payloads(tmp_path: Path):
    writer = build_run_store(tmp_path, run_id="agent-yesterday")
    written = writer.add(kind="forecast", created_by="forecast-1", summary="final", payload={"p": 0.07})

    blob_store = ArtifactStore(Settings(_env_file=None, runs_root=tmp_path, storage_mode="local"))
    opened = RunArtifactStore.open_run(blob_store, "agent-yesterday")

    assert [r.id for r in opened.all()] == [written.id]
    fetched = opened.get(written.id)
    assert fetched is not None and fetched.payload == {"p": 0.07}
    with pytest.raises(ReadOnlyRunError):
        opened.add(kind="quant", created_by="x", summary="s", payload={})
    with pytest.raises(MissingRunIndexError):
        RunArtifactStore.open_run(blob_store, "agent-never-ran")
