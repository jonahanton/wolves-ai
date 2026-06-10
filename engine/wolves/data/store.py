"""Dataset distribution; ids are digests of source hashes, never hand-bumped versions."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from pydantic import BaseModel

from wolves.config import Settings
from wolves.data.contracts import DatasetManifest
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import DATASET, DATASET_LATEST, DATASET_MANIFEST

logger = logging.getLogger(__name__)


class DatasetNotFoundError(Exception):
    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id
        super().__init__(f"dataset {dataset_id!r} not found locally or in the bucket")


class LatestPointer(BaseModel):
    dataset_id: str
    built_at: str
    tables: dict[str, int]


def dataset_id_from_hashes(source_hashes: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(source_hashes):
        digest.update(f"{name}={source_hashes[name]}".encode())
    return digest.hexdigest()[:12]


def dataset_filename(dataset_id: str) -> str:
    return Path(DATASET.key(dataset_id=dataset_id)).name


class DatasetStore:
    def __init__(self, settings: Settings) -> None:
        self._artifacts = ArtifactStore(settings)

    def publish(self, out_dir: Path, manifest: DatasetManifest) -> str:
        """Persist the built DuckDB, its manifest and the latest pointer."""
        dataset_id = manifest.dataset_id
        db_bytes = (out_dir / dataset_filename(dataset_id)).read_bytes()
        key = self._artifacts.put(DATASET, db_bytes, dataset_id=dataset_id)
        self._artifacts.put(DATASET_MANIFEST, manifest.model_dump_json(indent=2), dataset_id=dataset_id)
        pointer = LatestPointer(dataset_id=dataset_id, built_at=manifest.built_at, tables=manifest.tables)
        self._artifacts.put(DATASET_LATEST, pointer.model_dump_json(indent=2))
        logger.info("published dataset %s", dataset_id)
        return key

    def latest_id(self) -> str | None:
        body = self._artifacts.get(DATASET_LATEST)
        return LatestPointer.model_validate_json(body).dataset_id if body else None

    def fetch(self, *, dataset_id: str | None = None) -> tuple[Path, DatasetManifest]:
        """Return the local DuckDB path and manifest for the id (default latest)."""
        resolved = dataset_id or self.latest_id()
        if resolved is None:
            raise DatasetNotFoundError("latest")
        body = self._artifacts.get_binary(DATASET, dataset_id=resolved)
        manifest_text = self._artifacts.get(DATASET_MANIFEST, dataset_id=resolved)
        if body is None or manifest_text is None:
            raise DatasetNotFoundError(resolved)
        path = self._artifacts.local_path(DATASET.key(dataset_id=resolved))
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return path, DatasetManifest.model_validate_json(manifest_text)
