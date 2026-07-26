"""Build a reproducible static archive from immutable forecast objects."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from wolves.archive.contracts import (
    ARCHIVE_SCHEMA_HASH,
    ARCHIVE_TIMEZONE,
    ArchiveAuditDay,
    ArchiveAuditReport,
    ArchiveDay,
    ArchiveDayPayload,
    ArchiveForecastPoint,
    ArchiveManifest,
    ArchiveObject,
    ArchiveRun,
    ArchiveRunPayload,
)
from wolves.archive.errors import ArchiveExportError
from wolves.archive.selection import (
    ArchiveSelectionError,
    archive_cutoff,
    normalise_results,
    parse_timestamp,
    select_snapshot,
)
from wolves.archive.source import (
    ArchiveSource,
    CompleteSnapshot,
    FixtureMetadataSet,
    RunRecordSet,
    complete_snapshots,
    historical_live_days,
    load_fixture_metadata,
    load_run_records,
)
from wolves.archive.verify import verify_archive

logger = logging.getLogger(__name__)
ARCHIVE_FINAL_DAY = date(2026, 7, 20)


def export_archive(
    source: ArchiveSource,
    *,
    output: Path,
    days: list[str],
    run_records: RunRecordSet | None = None,
) -> ArchiveManifest:
    """Write a versioned archive bundle and return its checked manifest."""
    complete, rejected = complete_snapshots(source)
    if rejected:
        details = "; ".join(f"{key}: {reason}" for key, reason in sorted(rejected.items()))
        raise ArchiveExportError(f"incomplete archive sources: {details}")
    if not complete:
        raise ArchiveExportError("no complete snapshots found")

    root = output
    if root.exists():
        raise ArchiveExportError(f"archive output already exists: {root}")
    root.mkdir(parents=True)

    records = run_records or load_run_records(source)
    fixture_metadata = load_fixture_metadata(source, snapshots=complete)
    live_days = historical_live_days(source)
    entries: list[ArchiveDay] = []
    provenance: dict[str, list[dict[str, str | int | None]]] = {}
    try:
        ordered_days = _ordered_days(days)
        for day in ordered_days:
            entry, payload_sources = _export_day(
                root,
                day=day,
                complete=complete,
                records=records,
                fixture_metadata=fixture_metadata,
                live_detail="omitted" if day in live_days else "unavailable",
            )
            entries.append(entry)
            provenance[entry.payload.path] = [_source_record(obj) for obj in payload_sources]
        run_entries = _export_runs(
            root,
            complete=complete,
            records=records,
            days=entries,
            provenance=provenance,
        )
        manifest = ArchiveManifest(
            schema_hash=ARCHIVE_SCHEMA_HASH,
            generated_at=entries[-1].cutoff_at,
            archive_timezone=ARCHIVE_TIMEZONE,
            days=entries,
            runs=run_entries,
            final_day=entries[-1].day,
            default_route="/",
        )
        _write_model(root / "provenance.json", provenance)
        _write_model(root / "manifest.json", manifest)
        verify_archive(root, manifest)
    except Exception:
        _remove_empty_tree(root)
        raise
    return manifest


def audit_archive(source: ArchiveSource, *, days: list[str]) -> ArchiveAuditReport:
    """Return a deterministic per-day audit of archive source coverage."""
    complete, rejected = complete_snapshots(source)
    candidates = [item.snapshot for item in complete]
    by_run = {item.snapshot.run.run_id: item for item in complete}
    fixture_metadata = load_fixture_metadata(source, snapshots=complete)
    live_days = historical_live_days(source)
    report: list[ArchiveAuditDay] = []
    for day in _ordered_days(days):
        cutoff = archive_cutoff(day)
        live_detail = "omitted" if day in live_days else "unavailable"
        try:
            selected = select_snapshot(candidates, cutoff=cutoff)
            results = normalise_results(selected, cutoff=cutoff, fixture_metadata=fixture_metadata.fixtures)
            source_keys = [obj.key for obj in by_run[selected.run.run_id].source_objects]
            if fixture_metadata.source_object is not None:
                source_keys.append(fixture_metadata.source_object.key)
            report.append(
                ArchiveAuditDay(
                    day=day,
                    cutoff_at=cutoff.isoformat().replace("+00:00", "Z"),
                    selected_run_id=selected.run.run_id,
                    result_count=len(results),
                    live_detail=live_detail,
                    source_keys=sorted(set(source_keys)),
                )
            )
        except ArchiveSelectionError as exc:
            report.append(
                ArchiveAuditDay(
                    day=day,
                    cutoff_at=cutoff.isoformat().replace("+00:00", "Z"),
                    selected_run_id=None,
                    result_count=None,
                    live_detail=live_detail,
                    error=str(exc),
                )
            )
    return ArchiveAuditReport(days=report, rejected_sources=rejected)


def default_days(complete: list[CompleteSnapshot]) -> list[str]:
    """Return every calendar day covered by the complete snapshot range."""
    timezone = ZoneInfo(ARCHIVE_TIMEZONE)
    agent_snapshots = [item for item in complete if item.snapshot.run.kind == "agent"]
    covered_snapshots = agent_snapshots or complete
    represented = sorted(
        {
            parse_timestamp(item.snapshot.run.created_at).astimezone(timezone).date()
            for item in covered_snapshots
        }
    )
    if not represented:
        return []
    final_day = min(represented[-1], ARCHIVE_FINAL_DAY)
    return [
        (represented[0] + timedelta(days=offset)).isoformat()
        for offset in range((final_day - represented[0]).days + 1)
    ]


def _export_day(
    root: Path,
    *,
    day: str,
    complete: list[CompleteSnapshot],
    records: RunRecordSet,
    fixture_metadata: FixtureMetadataSet,
    live_detail: Literal["complete", "unavailable", "omitted"],
) -> tuple[ArchiveDay, tuple[object, ...]]:
    cutoff = archive_cutoff(day)
    by_run = {item.snapshot.run.run_id: item for item in complete}
    selected_snapshot = select_snapshot([item.snapshot for item in complete], cutoff=cutoff)
    selected = by_run[selected_snapshot.run.run_id]
    history = [
        item.snapshot
        for item in complete
        if item.snapshot.run.kind == "agent" and parse_timestamp(item.snapshot.run.created_at) <= cutoff
    ]
    history.sort(key=lambda snapshot: parse_timestamp(snapshot.run.created_at))
    records_by_run = {record.run_id: record for record in records.records}
    payload = ArchiveDayPayload(
        schema_hash=ARCHIVE_SCHEMA_HASH,
        day=day,
        cutoff_at=cutoff.isoformat().replace("+00:00", "Z"),
        selected_snapshot=selected.snapshot,
        sidecars=selected.sidecars,
        results=normalise_results(
            selected.snapshot,
            cutoff=cutoff,
            fixture_metadata=fixture_metadata.fixtures,
        ),
        forecast_history=[
            ArchiveForecastPoint(
                run=snapshot.run,
                teams=snapshot.teams,
                record=records_by_run.get(snapshot.run.run_id),
            )
            for snapshot in history
        ],
        live_detail=live_detail,
    )
    body = _model_bytes(payload)
    path = Path("days") / f"{hashlib.sha256(body).hexdigest()}.json"
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_bytes(body)
    entry = ArchiveDay(
        day=day,
        cutoff_at=payload.cutoff_at,
        forecast_run_id=selected.snapshot.run.run_id,
        forecast_created_at=selected.snapshot.run.created_at,
        live_detail=payload.live_detail,
        payload=ArchiveObject(path=path.as_posix(), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body)),
    )
    auxiliary_sources = tuple(
        obj
        for obj in (fixture_metadata.source_object, records.source_object)
        if obj is not None
    )
    history_sources = tuple(by_run[snapshot.run.run_id].snapshot_object for snapshot in history)
    return entry, _unique_sources((*selected.source_objects, *history_sources, *auxiliary_sources))


def _export_runs(
    root: Path,
    *,
    complete: list[CompleteSnapshot],
    records: RunRecordSet,
    days: list[ArchiveDay],
    provenance: dict[str, list[dict[str, str | int | None]]],
) -> list[ArchiveRun]:
    records_by_run = {record.run_id: record for record in records.records}
    final_cutoff = parse_timestamp(days[-1].cutoff_at)
    agent_runs = [
        item
        for item in complete
        if item.snapshot.run.kind == "agent"
        and parse_timestamp(item.snapshot.run.created_at) <= final_cutoff
    ]
    agent_runs.sort(key=lambda item: parse_timestamp(item.snapshot.run.created_at))
    entries: list[ArchiveRun] = []
    for item in agent_runs:
        payload = ArchiveRunPayload(
            schema_hash=ARCHIVE_SCHEMA_HASH,
            snapshot=item.snapshot,
            distributions=item.sidecars.distributions,
            record=records_by_run.get(item.snapshot.run.run_id),
        )
        body = _model_bytes(payload)
        digest = hashlib.sha256(body).hexdigest()
        path = Path("runs") / f"{digest}.json"
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(body)
        archive_day = next(
            day.day
            for day in days
            if parse_timestamp(item.snapshot.run.created_at) <= parse_timestamp(day.cutoff_at)
        )
        archive_object = ArchiveObject(path=path.as_posix(), sha256=digest, bytes=len(body))
        entries.append(
            ArchiveRun(
                run_id=item.snapshot.run.run_id,
                created_at=item.snapshot.run.created_at,
                archive_day=archive_day,
                payload=archive_object,
            )
        )
        sources = [item.snapshot_object, item.sidecar_objects["distributions"]]
        if records.source_object is not None and payload.record is not None:
            sources.append(records.source_object)
        provenance[path.as_posix()] = [_source_record(obj) for obj in _unique_sources(tuple(sources))]
    return entries


def _model_bytes(model: BaseModel) -> bytes:
    return json.dumps(model.model_dump(mode="json"), separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write_model(path: Path, model: BaseModel | dict[str, object]) -> None:
    body = (
        _model_bytes(model)
        if isinstance(model, BaseModel)
        else json.dumps(model, separators=(",", ":")).encode("utf-8")
    )
    path.write_bytes(body)


def _source_record(obj: object) -> dict[str, str | int | None]:
    from wolves.archive.source import SourceObject

    if not isinstance(obj, SourceObject):
        raise ArchiveExportError("unexpected archive provenance object")
    return {"key": obj.key, "version_id": obj.version_id, "sha256": obj.sha256, "bytes": len(obj.body)}


def _unique_sources(objects: tuple[object, ...]) -> tuple[object, ...]:
    from wolves.archive.source import SourceObject

    unique: dict[tuple[str, str | None, str], SourceObject] = {}
    for obj in objects:
        if not isinstance(obj, SourceObject):
            raise ArchiveExportError("unexpected archive provenance object")
        unique[(obj.key, obj.version_id, obj.sha256)] = obj
    return tuple(unique.values())


def _ordered_days(days: list[str]) -> list[str]:
    ordered = sorted(set(days))
    if not ordered:
        raise ArchiveExportError("at least one archive day is required")
    for day in ordered:
        archive_cutoff(day)
    return ordered


def _remove_empty_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    root.rmdir()
