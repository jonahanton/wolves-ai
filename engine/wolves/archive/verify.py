"""Verify a generated static archive."""

from __future__ import annotations

import hashlib
from pathlib import Path

from wolves.archive.contracts import (
    ARCHIVE_SCHEMA_HASH,
    ArchiveDayPayload,
    ArchiveManifest,
    ArchiveObject,
    ArchiveRunPayload,
)
from wolves.archive.errors import ArchiveExportError
from wolves.archive.selection import parse_timestamp


def verify_archive(root: Path, manifest: ArchiveManifest) -> None:
    """Reject a manifest with missing or altered payloads."""
    if manifest.schema_hash != ARCHIVE_SCHEMA_HASH:
        raise ArchiveExportError("manifest schema hash differs from the current archive contract")
    for day in manifest.days:
        _verify_object(root, day.payload)
        payload = ArchiveDayPayload.model_validate_json((root / day.payload.path).read_bytes())
        if payload.schema_hash != manifest.schema_hash:
            raise ArchiveExportError(f"payload schema hash differs: {day.payload.path}")
        cutoff = parse_timestamp(payload.cutoff_at)
        if any(parse_timestamp(result.recorded_at) > cutoff for result in payload.results):
            raise ArchiveExportError(f"payload discloses a post-cutoff result: {day.payload.path}")
    for run in manifest.runs:
        _verify_object(root, run.payload)
        payload = ArchiveRunPayload.model_validate_json((root / run.payload.path).read_bytes())
        if payload.schema_hash != manifest.schema_hash or payload.snapshot.run.run_id != run.run_id:
            raise ArchiveExportError(f"run payload contract differs: {run.payload.path}")


def _verify_object(root: Path, archive_object: ArchiveObject) -> None:
    path = root / archive_object.path
    if not path.is_file():
        raise ArchiveExportError(f"manifest payload is missing: {archive_object.path}")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != archive_object.sha256:
        raise ArchiveExportError(f"payload digest differs: {archive_object.path}")
    if len(body) != archive_object.bytes:
        raise ArchiveExportError(f"payload size differs: {archive_object.path}")
