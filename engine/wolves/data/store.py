"""Dataset distribution. A dataset's identity is a digest of its source
hashes, so identical inputs rebuild to the same id and any source change mints
a new one; nobody hand-bumps versions. datasets/latest.json points at the id
runs should use unless they pin one."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from pydantic import BaseModel

from wolves.config import Settings
from wolves.data.contracts import DatasetManifest
from wolves.store.artifacts import ArtifactStore

logger = logging.getLogger(__name__)

PREFIX = "datasets"
LATEST_KEY = f"{PREFIX}/latest.json"


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
    return f"wolves-data-{dataset_id}.duckdb"


class DatasetStore:
    def __init__(self, settings: Settings) -> None:
        self._artifacts = ArtifactStore(settings)

    def publish(self, out_dir: Path, manifest: DatasetManifest) -> str:
        """Persist the built DuckDB, its manifest and the latest pointer."""
        filename = dataset_filename(manifest.dataset_id)
        key = f"{PREFIX}/{filename}"
        self._artifacts.put_bytes(key, (out_dir / filename).read_bytes())
        self._artifacts.put_text(f"{key}.manifest.json", manifest.model_dump_json(indent=2))
        pointer = LatestPointer(dataset_id=manifest.dataset_id, built_at=manifest.built_at, tables=manifest.tables)
        self._artifacts.put_text(LATEST_KEY, pointer.model_dump_json(indent=2))
        logger.info("published dataset %s", manifest.dataset_id)
        return key

    def latest_id(self) -> str | None:
        body = self._artifacts.get_text(LATEST_KEY, prefer="s3")
        return LatestPointer.model_validate_json(body).dataset_id if body else None

    def fetch(self, *, dataset_id: str | None = None) -> tuple[Path, DatasetManifest]:
        """Return the local DuckDB path and manifest for the id (default latest)."""
        resolved = dataset_id or self.latest_id()
        if resolved is None:
            raise DatasetNotFoundError("latest")
        filename = dataset_filename(resolved)
        body = self._artifacts.get_bytes(f"{PREFIX}/{filename}")
        manifest_text = self._artifacts.get_text(f"{PREFIX}/{filename}.manifest.json")
        if body is None or manifest_text is None:
            raise DatasetNotFoundError(resolved)
        path = self._artifacts.local_path(f"{PREFIX}/{filename}")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return path, DatasetManifest.model_validate_json(manifest_text)
