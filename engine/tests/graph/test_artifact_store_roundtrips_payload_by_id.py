from __future__ import annotations

import json
import re
from pathlib import Path

from wolves.graph.artifacts import ArtifactStore


def test_roundtrip(tmp_path: Path):
    store = ArtifactStore(tmp_path / "artifacts")
    payload = {"summary": "keeper fit", "evidence": [{"claim": "trained in full"}]}

    artifact = store.add(kind="evidence", created_by="research-keeper", summary="keeper fit", payload=payload)

    assert re.fullmatch(r"evidence-[0-9a-f]{8}", artifact.id)
    assert store.has(artifact.id)
    fetched = store.get(artifact.id)
    assert fetched is not None
    assert fetched.payload == payload
    assert fetched.created_by == "research-keeper"

    on_disk = json.loads((tmp_path / "artifacts" / f"{artifact.id}.json").read_text(encoding="utf-8"))
    assert on_disk["payload"] == payload

    assert store.get("evidence-deadbeef") is None
    assert not store.has("evidence-deadbeef")
