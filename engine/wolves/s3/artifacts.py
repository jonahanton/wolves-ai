"""Local-first store for the layout key space, mirrored per the storage mode."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from wolves.s3.client import S3Client
from wolves.s3.layout import BINARY, JSON, MARKDOWN, NDJSON, ArtifactSpec, StorageMode

if TYPE_CHECKING:
    from wolves.config import Settings

logger = logging.getLogger(__name__)

_SUFFIX_CONTENT_TYPES = {".json": JSON, ".jsonl": NDJSON, ".md": MARKDOWN}


def _content_type(key: str) -> str:
    return _SUFFIX_CONTENT_TYPES.get(Path(key).suffix, BINARY)


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

    def put(self, spec: ArtifactSpec, body: str | bytes, **parts: str) -> str:
        """Write one artifact; the spec supplies the key and content type."""
        key = spec.key(**parts)
        if isinstance(body, bytes):
            self.put_bytes(key, body)
        else:
            self.put_text(key, body, content_type=spec.content_type)
        return key

    def get(self, spec: ArtifactSpec, **parts: str) -> str | None:
        """Read one text artifact; the spec decides which side is authoritative."""
        return self.get_text(spec.key(**parts), prefer=spec.prefer)

    def get_binary(self, spec: ArtifactSpec, **parts: str) -> bytes | None:
        return self.get_bytes(spec.key(**parts), prefer=spec.prefer)

    def put_text(self, key: str, body: str, *, content_type: str = "application/json") -> None:
        # Local write first, so an S3 outage is loud without losing data.
        if self.mode != "s3":
            self._write_local(key, body.encode("utf-8"))
        if self._s3 is not None:
            self._s3.put_text(key, body, content_type=content_type)

    def put_bytes(self, key: str, body: bytes) -> None:
        if self.mode != "s3":
            self._write_local(key, body)
        if self._s3 is not None:
            self._s3.put_bytes(key, body)

    def _write_local(self, key: str, body: bytes) -> None:
        # Atomic replace: a crash mid-write must not leave a torn mutable key.
        path = self.local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_bytes(body)
        tmp.replace(path)

    def get_text(self, key: str, *, prefer: Literal["local", "s3"] = "local") -> str | None:
        body = self.get_bytes(key, prefer=prefer)
        return body.decode("utf-8") if body is not None else None

    def get_bytes(self, key: str, *, prefer: Literal["local", "s3"] = "local") -> bytes | None:
        path = self.local_path(key)
        if prefer == "local" and self.mode != "s3" and path.exists():
            return path.read_bytes()
        if self._s3 is not None:
            body = self._s3.get_bytes(key)
            if body is not None:
                if self.mode in ("both", "s3"):
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

    def sync_up(self, *, prefix: str) -> int:
        """Upload local files under the prefix missing from the bucket; returns the count.

        Skips keys already in the bucket, so it suits immutable families;
        mutable pointers go through put(), which always overwrites."""
        if self._s3 is None:
            return 0
        base = self.local_path(prefix)
        if not base.exists():
            return 0
        existing = set(self._s3.list_keys(prefix=prefix))
        uploaded = 0
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            key = path.relative_to(self.local_root).as_posix()
            if key in existing:
                continue
            self._s3.put_bytes(key, path.read_bytes(), content_type=_content_type(key))
            uploaded += 1
        if uploaded:
            logger.info("synced %d object(s) under %s to s3://%s", uploaded, prefix, self.bucket)
        return uploaded

    def sync_down(self, *, prefix: str, suffix: str = "", contains: str = "", into: Path | None = None) -> int:
        """Download bucket objects missing locally; returns the new-file count.

        Destinations mirror the key under the local root, or under `into`
        (relative to the prefix) for trees consumed outside the mirror."""
        if self._s3 is None:
            return 0
        downloaded = 0
        for key in self._s3.list_keys(prefix=prefix):
            if contains and contains not in key:
                continue
            if suffix and not key.endswith(suffix):
                continue
            destination = self.local_path(key) if into is None else into / key.removeprefix(prefix)
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
