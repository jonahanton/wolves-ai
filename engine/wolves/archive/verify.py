"""Verify a generated static archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wolves.archive.contracts import (
    ARCHIVE_SCHEMA_HASH,
    ARCHIVE_TIMEZONE,
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
    if not manifest.days:
        raise ArchiveExportError("manifest has no archive days")
    if [day.day for day in manifest.days] != sorted({day.day for day in manifest.days}):
        raise ArchiveExportError("manifest days are not unique and ordered")
    if manifest.final_day != manifest.days[-1].day:
        raise ArchiveExportError("manifest final day differs from its last archive day")
    if manifest.default_route != "/" or manifest.archive_timezone != ARCHIVE_TIMEZONE:
        raise ArchiveExportError("manifest routing or timezone differs from the archive contract")
    expected_paths: set[str] = set()
    for day in manifest.days:
        _verify_object(root, day.payload)
        expected_paths.add(day.payload.path)
        payload = _load_payload(root / day.payload.path, ArchiveDayPayload)
        if payload.schema_hash != manifest.schema_hash:
            raise ArchiveExportError(f"payload schema hash differs: {day.payload.path}")
        if (
            payload.day != day.day
            or payload.cutoff_at != day.cutoff_at
            or payload.selected_snapshot.run.run_id != day.forecast_run_id
            or payload.selected_snapshot.run.created_at != day.forecast_created_at
            or payload.live_detail != day.live_detail
        ):
            raise ArchiveExportError(f"day payload contract differs: {day.payload.path}")
        cutoff = parse_timestamp(payload.cutoff_at)
        if any(parse_timestamp(result.recorded_at) > cutoff for result in payload.results):
            raise ArchiveExportError(f"payload discloses a post-cutoff result: {day.payload.path}")
    for run in manifest.runs:
        _verify_object(root, run.payload)
        expected_paths.add(run.payload.path)
        payload = _load_payload(root / run.payload.path, ArchiveRunPayload)
        if (
            payload.schema_hash != manifest.schema_hash
            or payload.snapshot.run.run_id != run.run_id
            or payload.snapshot.run.created_at != run.created_at
        ):
            raise ArchiveExportError(f"run payload contract differs: {run.payload.path}")
        archive_day = next(
            (
                day.day
                for day in manifest.days
                if parse_timestamp(run.created_at) <= parse_timestamp(day.cutoff_at)
            ),
            None,
        )
        if archive_day != run.archive_day:
            raise ArchiveExportError(f"run archive day differs: {run.payload.path}")
    _verify_provenance(root, expected_paths)


def _verify_object(root: Path, archive_object: ArchiveObject) -> None:
    path = root / archive_object.path
    if not path.is_file():
        raise ArchiveExportError(f"manifest payload is missing: {archive_object.path}")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != archive_object.sha256:
        raise ArchiveExportError(f"payload digest differs: {archive_object.path}")
    if len(body) != archive_object.bytes:
        raise ArchiveExportError(f"payload size differs: {archive_object.path}")


def _load_payload[T: ArchiveDayPayload | ArchiveRunPayload](path: Path, model: type[T]) -> T:
    try:
        return model.model_validate_json(path.read_bytes())
    except ValidationError as exc:
        raise ArchiveExportError(f"invalid archive payload: {path.name}") from exc


def _verify_provenance(root: Path, expected_paths: set[str]) -> None:
    path = root / "provenance.json"
    try:
        provenance: Any = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveExportError("archive provenance is missing or invalid") from exc
    if not isinstance(provenance, dict) or set(provenance) != expected_paths:
        raise ArchiveExportError("archive provenance does not cover exactly the manifest payloads")
    for output_path, sources in provenance.items():
        if not isinstance(sources, list) or not sources:
            raise ArchiveExportError(f"archive provenance has no sources: {output_path}")
        for source in sources:
            if (
                not isinstance(source, dict)
                or not isinstance(source.get("key"), str)
                or not isinstance(source.get("bytes"), int)
                or source["bytes"] < 0
                or not isinstance(source.get("sha256"), str)
                or len(source["sha256"]) != 64
                or any(character not in "0123456789abcdef" for character in source["sha256"])
                or (
                    source.get("version_id") is not None
                    and not isinstance(source["version_id"], str)
                )
            ):
                raise ArchiveExportError(f"archive provenance source is invalid: {output_path}")
