from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

ArtifactKind = Literal["evidence", "quant", "draft_forecast", "critique"]


class Artifact(BaseModel):
    id: str
    kind: ArtifactKind
    created_by: str
    summary: str
    payload: dict[str, Any]


class ArtifactStore:
    """In-memory artifact index persisted to the run directory on creation.

    ``add`` is safe under concurrent node execution only because the
    synchronous ``write_text`` never yields to the event loop; do not swap
    in async file I/O without adding a lock around write-and-index."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, Artifact] = {}

    def add(self, *, kind: ArtifactKind, created_by: str, summary: str, payload: dict[str, Any]) -> Artifact:
        artifact = Artifact(
            id=f"{kind}-{uuid.uuid4().hex[:8]}",
            kind=kind,
            created_by=created_by,
            summary=summary,
            payload=payload,
        )
        (self._root / f"{artifact.id}.json").write_text(artifact.model_dump_json(indent=1), encoding="utf-8")
        self._index[artifact.id] = artifact
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._index.get(artifact_id)

    def has(self, artifact_id: str) -> bool:
        return artifact_id in self._index

    def all(self) -> list[Artifact]:
        return list(self._index.values())
