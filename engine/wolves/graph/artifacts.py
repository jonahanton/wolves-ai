from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import RUN_ARTIFACT, RUN_ARTIFACT_INDEX

ArtifactKind = Literal[
    "evidence",
    "quant",
    "draft_forecast",
    "critique",
    "retrieval",
    "mixture",
    "forecast",
    "report",
]


class ArtifactRecord(BaseModel):
    """Metadata for one artifact; the payload lives in its own blob."""

    id: str
    kind: ArtifactKind
    created_by: str
    summary: str
    created_at: datetime
    workspace_prefix: str | None = None


class Artifact(ArtifactRecord):
    payload: dict[str, Any]


class ArtifactIndex(BaseModel):
    run_id: str
    records: list[ArtifactRecord] = Field(default_factory=list)


class MissingRunIndexError(Exception):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"run {run_id!r} has no artifact index")


class ReadOnlyRunError(Exception):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"run {run_id!r} was opened read-only")


class RunArtifactStore:
    """Sequentially-addressed artifacts for one run, written under the
    canonical layout so other runs can open them by the same keys.

    Writes are local during the run (run end pushes the prefix to S3 with
    the rest of the run state); ``add`` never yields to the event loop,
    so concurrent node completions cannot interleave id allocation."""

    def __init__(self, store: ArtifactStore, run_id: str) -> None:
        self._store = store
        self.run_id = run_id
        self._readonly = False
        self._cache: dict[str, Artifact] = {}
        self._records: dict[str, ArtifactRecord] = {}
        self._counts: dict[str, int] = {}

    @classmethod
    def open_run(cls, store: ArtifactStore, run_id: str) -> RunArtifactStore:
        """Open a finished run's artifacts read-only, S3-hydrated if needed."""
        body = store.get(RUN_ARTIFACT_INDEX, run_id=run_id)
        if body is None:
            raise MissingRunIndexError(run_id)
        opened = cls(store, run_id)
        opened._readonly = True
        for record in ArtifactIndex.model_validate_json(body).records:
            opened._records[record.id] = record
        return opened

    def add(
        self,
        *,
        kind: ArtifactKind,
        created_by: str,
        summary: str,
        payload: dict[str, Any],
        workspace_prefix: str | None = None,
    ) -> Artifact:
        if self._readonly:
            raise ReadOnlyRunError(self.run_id)
        seq = self._counts.get(kind, 0) + 1
        self._counts[kind] = seq
        artifact = Artifact(
            id=f"{kind}-{seq:03d}",
            kind=kind,
            created_by=created_by,
            summary=summary,
            created_at=datetime.now(UTC),
            workspace_prefix=workspace_prefix,
            payload=payload,
        )
        key = RUN_ARTIFACT.key(run_id=self.run_id, artifact_id=artifact.id)
        self._write_local(key, artifact.model_dump_json(indent=1))
        self._cache[artifact.id] = artifact
        self._records[artifact.id] = ArtifactRecord.model_validate(artifact.model_dump(exclude={"payload"}))
        self._write_local(RUN_ARTIFACT_INDEX.key(run_id=self.run_id), self.index().model_dump_json(indent=1))
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        cached = self._cache.get(artifact_id)
        if cached is not None:
            return cached
        if artifact_id not in self._records:
            return None
        body = self._store.get(RUN_ARTIFACT, run_id=self.run_id, artifact_id=artifact_id)
        if body is None:
            return None
        artifact = Artifact.model_validate_json(body)
        self._cache[artifact_id] = artifact
        return artifact

    def record(self, artifact_id: str) -> ArtifactRecord | None:
        return self._records.get(artifact_id)

    def has(self, artifact_id: str) -> bool:
        return artifact_id in self._records

    def all(self) -> list[ArtifactRecord]:
        return list(self._records.values())

    def index(self) -> ArtifactIndex:
        return ArtifactIndex(run_id=self.run_id, records=self.all())

    def workspace_files(self, artifact_id: str) -> list[str]:
        """Relative paths under the artifact's workspace prefix, if it has one."""
        record = self._records.get(artifact_id)
        if record is None or record.workspace_prefix is None:
            return []
        base = self._store.local_path(record.workspace_prefix)
        if not base.exists():
            return []
        return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())

    def workspace_path(self, artifact_id: str) -> str | None:
        """Absolute local path of the artifact's workspace prefix, if any."""
        record = self._records.get(artifact_id)
        if record is None or record.workspace_prefix is None:
            return None
        return str(self._store.local_path(record.workspace_prefix))

    def _write_local(self, key: str, body: str) -> None:
        path = self._store.local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
