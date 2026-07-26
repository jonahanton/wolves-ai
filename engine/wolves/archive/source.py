"""Read validated immutable forecast inputs from local storage or S3."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import boto3
from pydantic import BaseModel, ValidationError

from wolves.archive.contracts import ArchiveRunRecord, ArchiveSidecars
from wolves.s3.index import RunIndex
from wolves.sidecars import sidecar_dataset
from wolves.snapshot import Snapshot

REQUIRED_SIDECARS = ("distributions", "bracket-samples", "pairing-matrices", "match-wdl-draws")
SNAPSHOT_KEY = re.compile(r"(?:^|/)snapshots/\d{4}/\d{2}/\d{2}/(?P<run_id>[^/.]+)\.json$")
LIVE_HISTORY_KEY = re.compile(r"(?:^|/)live/history/(?P<day>\d{4}-\d{2}-\d{2})/")


class ArchiveSourceError(ValueError):
    """An archive input is missing or violates its published contract."""


@dataclass(frozen=True)
class SourceObject:
    key: str
    body: bytes
    version_id: str | None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


@dataclass(frozen=True)
class CompleteSnapshot:
    snapshot: Snapshot
    sidecars: ArchiveSidecars
    snapshot_object: SourceObject
    sidecar_objects: dict[str, SourceObject]

    @property
    def source_objects(self) -> tuple[SourceObject, ...]:
        return (self.snapshot_object, *(self.sidecar_objects[name] for name in REQUIRED_SIDECARS))


@dataclass(frozen=True)
class FixtureMetadata:
    date: str
    stage: str


@dataclass(frozen=True)
class FixtureMetadataSet:
    fixtures: dict[int, FixtureMetadata]
    source_object: SourceObject | None


@dataclass(frozen=True)
class RunRecordSet:
    records: list[ArchiveRunRecord]
    source_object: SourceObject | None


class ArchiveSource(Protocol):
    def list_keys(self, *, prefix: str) -> list[str]: ...
    def read(self, key: str) -> SourceObject: ...


class LocalArchiveSource:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def list_keys(self, *, prefix: str) -> list[str]:
        directory = self._root / prefix
        if not directory.exists():
            return []
        return sorted(path.relative_to(self._root).as_posix() for path in directory.rglob("*") if path.is_file())

    def read(self, key: str) -> SourceObject:
        path = self._root / key
        if not path.is_file():
            raise ArchiveSourceError(f"missing source object {key}")
        return SourceObject(key=key, body=path.read_bytes(), version_id=None)


class S3ArchiveSource:
    def __init__(self, bucket: str, *, prefix: str = "", region: str | None = None) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._client = boto3.client("s3", region_name=region)
        self._version_ids: dict[str, str] = {}

    def list_keys(self, *, prefix: str) -> list[str]:
        full_prefix = self._physical_key(prefix.strip("/"))
        if full_prefix:
            full_prefix = f"{full_prefix}/"
        newest: dict[str, tuple[datetime, str]] = {}
        paginator = self._client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
            for version in page.get("Versions", []):
                key = version["Key"]
                if key not in newest or version["LastModified"] > newest[key][0]:
                    newest[key] = (version["LastModified"], version["VersionId"])
        logical_keys = [self._logical_key(key) for key in newest]
        self._version_ids.update(
            {
                self._logical_key(key): version_id
                for key, (_, version_id) in newest.items()
            }
        )
        return sorted(logical_keys)

    def read(self, key: str) -> SourceObject:
        version_id = self._version_ids.get(key) or self._find_latest_version(key)
        if version_id is None:
            raise ArchiveSourceError(f"missing source object {key}")
        response = self._client.get_object(
            Bucket=self._bucket,
            Key=self._physical_key(key),
            VersionId=version_id,
        )
        return SourceObject(key=key, body=response["Body"].read(), version_id=version_id)

    def _find_latest_version(self, key: str) -> str | None:
        physical_key = self._physical_key(key)
        response = self._client.list_object_versions(Bucket=self._bucket, Prefix=physical_key)
        versions = [
            version
            for version in response.get("Versions", [])
            if version["Key"] == physical_key
        ]
        if not versions:
            return None
        latest = max(versions, key=lambda version: version["LastModified"])
        version_id = latest["VersionId"]
        self._version_ids[key] = version_id
        return version_id

    def _physical_key(self, key: str) -> str:
        return "/".join(part for part in (self._prefix, key.strip("/")) if part)

    def _logical_key(self, key: str) -> str:
        if not self._prefix:
            return key
        return key.removeprefix(f"{self._prefix}/")


def complete_snapshots(source: ArchiveSource) -> tuple[list[CompleteSnapshot], dict[str, str]]:
    """Load every complete snapshot and report rejected snapshot inputs."""
    complete: list[CompleteSnapshot] = []
    rejected: dict[str, str] = {}
    for key in source.list_keys(prefix="snapshots"):
        match = SNAPSHOT_KEY.search(key)
        if match is None:
            continue
        try:
            complete.append(_load_complete_snapshot(source, key, match.group("run_id")))
        except ArchiveSourceError as exc:
            rejected[key] = str(exc)
    return complete, rejected


def load_run_records(source: ArchiveSource, *, key: str = "archive-run-records.json") -> RunRecordSet:
    """Load optional recorded run metadata without fabricating unavailable values."""
    try:
        obj = source.read(key)
    except ArchiveSourceError:
        return RunRecordSet(records=[], source_object=None)
    try:
        raw = json.loads(obj.body)
        rows = raw.get("runs", raw) if isinstance(raw, dict) else raw
        return RunRecordSet(
            records=[ArchiveRunRecord.model_validate(row) for row in rows],
            source_object=obj,
        )
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ArchiveSourceError(f"invalid run record source {key}: {exc}") from exc


def load_dynamo_run_records(*, table_name: str, region: str) -> RunRecordSet:
    """Read the production run index into an immutable archive source object."""
    indexed = RunIndex(table_name=table_name, region=region).list_runs(limit=10_000)
    records = [
        ArchiveRunRecord(
            run_id=record.run_id,
            created_at=record.created_at,
            status=record.status,
            cost=record.cost,
            duration_s=record.duration_s,
            kind=record.kind,
        )
        for record in indexed
    ]
    body = json.dumps(
        {"runs": [record.model_dump(mode="json") for record in records]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return RunRecordSet(
        records=records,
        source_object=SourceObject(
            key=f"dynamodb://{table_name}/RUN",
            body=body,
            version_id=None,
        ),
    )


def load_fixture_metadata(
    source: ArchiveSource,
    *,
    snapshots: list[CompleteSnapshot],
    key: str = "live/results.json",
) -> FixtureMetadataSet:
    """Load schedule metadata without taking scores from mutable live state."""
    try:
        source_object = source.read(key)
    except ArchiveSourceError:
        return FixtureMetadataSet(fixtures={}, source_object=None)
    try:
        raw = json.loads(source_object.body)
        fixture_dates = {
            fixture["fixture_id"]: fixture["kickoff"] for fixture in raw.get("fixtures", [])
        }
        fixture_matches = {
            result.source_fixture_id: result.match
            for complete in snapshots
            for result in complete.snapshot.result_set.results
            if result.source_fixture_id is not None
        }
        return FixtureMetadataSet(
            fixtures={
                match: FixtureMetadata(date=fixture_dates[fixture_id], stage=_stage_for_match(match))
                for fixture_id, match in fixture_matches.items()
                if fixture_id in fixture_dates
            },
            source_object=source_object,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ArchiveSourceError(f"invalid fixture metadata source {key}: {exc}") from exc


def _stage_for_match(match: str | int) -> str:
    number = int(match)
    if number <= 72:
        return "group"
    if number <= 88:
        return "r32"
    if number <= 96:
        return "r16"
    if number <= 100:
        return "qf"
    if number <= 102:
        return "sf"
    return "third_place" if number == 103 else "final"


def historical_live_days(source: ArchiveSource) -> set[str]:
    """Return days with retained live-history objects."""
    return {
        match.group("day")
        for key in source.list_keys(prefix="live/history")
        if (match := LIVE_HISTORY_KEY.search(key)) is not None
    }


def _load_complete_snapshot(source: ArchiveSource, key: str, run_id: str) -> CompleteSnapshot:
    snapshot_object = source.read(key)
    try:
        snapshot = Snapshot.model_validate_json(snapshot_object.body)
    except ValidationError as exc:
        raise ArchiveSourceError(f"invalid snapshot {key}: {exc}") from exc
    _reject_source_loss(snapshot_object, snapshot)
    if snapshot.run.run_id != run_id:
        raise ArchiveSourceError(f"snapshot key {key} disagrees with run id {snapshot.run.run_id}")

    sidecars: dict[str, object] = {}
    sidecar_objects: dict[str, SourceObject] = {}
    for name in REQUIRED_SIDECARS:
        sidecar_key = key.removesuffix(".json") + f".{name}.json"
        try:
            sidecar_object = source.read(sidecar_key)
        except ArchiveSourceError as exc:
            raise ArchiveSourceError(f"{run_id} lacks required {name} sidecar: {sidecar_key}") from exc
        try:
            sidecars[name] = sidecar_dataset(name).model.model_validate_json(sidecar_object.body)
        except ValidationError as exc:
            raise ArchiveSourceError(f"invalid {name} sidecar {sidecar_key}: {exc}") from exc
        _reject_source_loss(sidecar_object, sidecars[name])
        sidecar_objects[name] = sidecar_object

    return CompleteSnapshot(
        snapshot=snapshot,
        sidecars=ArchiveSidecars(
            distributions=sidecars["distributions"],
            bracket_samples=sidecars["bracket-samples"],
            pairing_matrices=sidecars["pairing-matrices"],
            match_wdl_draws=sidecars["match-wdl-draws"],
        ),
        snapshot_object=snapshot_object,
        sidecar_objects=sidecar_objects,
    )


def _reject_source_loss(source: SourceObject, model: object) -> None:
    if not isinstance(model, BaseModel):
        raise ArchiveSourceError(f"invalid archive model for {source.key}")
    raw = json.loads(source.body)
    difference = _first_source_difference(raw, model.model_dump(mode="json"), path="$")
    if difference is not None:
        raise ArchiveSourceError(f"{source.key} would lose source data at {difference}")


def _first_source_difference(source: object, archived: object, *, path: str) -> str | None:
    if isinstance(source, dict):
        if not isinstance(archived, dict):
            return path
        for key, value in source.items():
            if key not in archived:
                return f"{path}.{key}"
            difference = _first_source_difference(value, archived[key], path=f"{path}.{key}")
            if difference is not None:
                return difference
        return None
    if isinstance(source, list):
        if not isinstance(archived, list) or len(source) != len(archived):
            return path
        for index, value in enumerate(source):
            difference = _first_source_difference(value, archived[index], path=f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    return None if source == archived else path
