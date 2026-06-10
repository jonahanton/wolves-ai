"""One artifact store for every blob the app persists. A single canonical key
space (snapshots/, runs/, datasets/, models/, odds-archive/, agent-state/) is
mirrored between the local runs root and the bucket, so dev and production
share one layout and restore is a generic sync. Writes are local-first so an
S3 outage is loud without losing data; reads are cache-first so fresh
containers hydrate themselves."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from wolves.clients.s3.client import S3Client

if TYPE_CHECKING:
    from wolves.config import Settings

logger = logging.getLogger(__name__)

BUCKET_DEV = "wolves-superforecaster-dev"
BUCKET_PROD = "wolves-superforecaster-prod"

StorageMode = Literal["local", "s3", "both"]


class StorageConfigError(Exception):
    def __init__(self, mode: str, bucket: str) -> None:
        self.mode = mode
        self.bucket = bucket
        super().__init__(f"storage mode {mode!r} needs a bucket; got {bucket!r}")


class ArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self.mode: StorageMode = settings.storage_mode
        self.bucket = settings.bucket
        self.local_root = settings.runs_root
        if self.mode in ("s3", "both") and not self.bucket:
            raise StorageConfigError(self.mode, self.bucket)
        self._s3 = S3Client(bucket=self.bucket, region=settings.aws_region) if self.mode != "local" else None

    def local_path(self, key: str) -> Path:
        return self.local_root / key

    def put_text(self, key: str, body: str, *, content_type: str = "application/json") -> None:
        if self.mode != "s3":
            path = self.local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        if self._s3 is not None:
            self._s3.put_text(key, body, content_type=content_type)

    def put_bytes(self, key: str, body: bytes) -> None:
        if self.mode != "s3":
            path = self.local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        if self._s3 is not None:
            self._s3.put_bytes(key, body)

    def get_text(self, key: str, *, prefer: Literal["local", "s3"] = "local") -> str | None:
        """Read an artifact. Immutable artifacts read local-first (the cache);
        mutable pointers pass prefer="s3" because the bucket is authoritative."""
        path = self.local_path(key)
        if prefer == "local" and self.mode != "s3" and path.exists():
            return path.read_text(encoding="utf-8")
        if self._s3 is not None:
            body = self._s3.get_text(key)
            if body is not None:
                if self.mode == "both":
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(body, encoding="utf-8")
                return body
        if self.mode != "s3" and path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def get_bytes(self, key: str, *, prefer: Literal["local", "s3"] = "local") -> bytes | None:
        path = self.local_path(key)
        if prefer == "local" and self.mode != "s3" and path.exists():
            return path.read_bytes()
        if self._s3 is not None:
            body = self._s3.get_bytes(key)
            if body is not None:
                if self.mode == "both":
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
                return body
        if self.mode != "s3" and path.exists():
            return path.read_bytes()
        return None

    def list_keys(self, *, prefix: str) -> list[str]:
        keys: set[str] = set()
        if self.mode != "s3":
            base = self.local_path(prefix)
            if base.exists():
                keys |= {str(p.relative_to(self.local_root)) for p in base.rglob("*") if p.is_file()}
        if self._s3 is not None:
            keys |= set(self._s3.list_keys(prefix=prefix))
        return sorted(keys)

    def sync_down(self, *, prefix: str, suffix: str = "") -> int:
        """Hydrate the local mirror with bucket objects it lacks; returns new files."""
        if self._s3 is None or self.mode == "s3":
            return 0
        downloaded = 0
        for key in self._s3.list_keys(prefix=prefix):
            if suffix and not key.endswith(suffix):
                continue
            destination = self.local_path(key)
            if destination.exists():
                continue
            body = self._s3.get_bytes(key)
            if body is None:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
            downloaded += 1
        if downloaded:
            logger.info("synced %d object(s) under %s from s3://%s", downloaded, prefix, self.bucket)
        return downloaded
