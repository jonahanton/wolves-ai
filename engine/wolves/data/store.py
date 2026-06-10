"""Dataset distribution: push built datasets to S3 and pull them by version.

The DuckDB file is the unit of exchange; parquet mirrors stay local build
artifacts. Fetch is cache-first so runs in the same environment download once."""

from __future__ import annotations

import logging
from pathlib import Path

from wolves.clients.s3.client import S3Client
from wolves.config import Settings
from wolves.data.build import dataset_filename
from wolves.data.contracts import DatasetManifest

logger = logging.getLogger(__name__)

S3_PREFIX = "datasets"


class DatasetNotFoundError(Exception):
    def __init__(self, version: str, bucket: str) -> None:
        self.version = version
        self.bucket = bucket
        super().__init__(f"dataset {version!r} not found in bucket {bucket!r}")


class DatasetStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache_dir = settings.runs_root / "datasets"

    def publish(self, out_dir: Path, *, version: str) -> str:
        """Upload the built DuckDB and manifest; return the dataset key."""
        filename = dataset_filename(version)
        s3 = S3Client(bucket=self._settings.agent_state_bucket, region=self._settings.aws_region)
        key = f"{S3_PREFIX}/{filename}"
        s3.put_bytes(key, (out_dir / filename).read_bytes())
        s3.put_text(
            f"{key}.manifest.json",
            (out_dir / f"{filename}.manifest.json").read_text(encoding="utf-8"),
            content_type="application/json",
        )
        logger.info("published dataset %s to s3://%s/%s", version, self._settings.agent_state_bucket, key)
        return key

    def fetch(self, *, version: str) -> tuple[Path, DatasetManifest]:
        """Return the local DuckDB path and manifest, downloading on cache miss."""
        filename = dataset_filename(version)
        db_path = self._cache_dir / filename
        manifest_path = self._cache_dir / f"{filename}.manifest.json"
        if db_path.exists() and manifest_path.exists():
            return db_path, DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

        s3 = S3Client(bucket=self._settings.agent_state_bucket, region=self._settings.aws_region)
        body = s3.get_bytes(f"{S3_PREFIX}/{filename}")
        manifest_text = s3.get_text(f"{S3_PREFIX}/{filename}.manifest.json")
        if body is None or manifest_text is None:
            raise DatasetNotFoundError(version, self._settings.agent_state_bucket)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(body)
        manifest_path.write_text(manifest_text, encoding="utf-8")
        logger.info("fetched dataset %s from S3 into %s", version, db_path)
        return db_path, DatasetManifest.model_validate_json(manifest_text)
