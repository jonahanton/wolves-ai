"""Define the versioned browser archive contract."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field

from wolves.sidecars import BracketSamples, DistributionsSidecar, MatchWdlDraws, PairingMatrices
from wolves.snapshot import RunMeta, Snapshot, TeamInfo

ARCHIVE_TIMEZONE = "America/New_York"


class ArchiveObject(BaseModel):
    path: str
    sha256: str
    bytes: int


class ArchiveDay(BaseModel):
    day: str
    cutoff_at: str
    forecast_run_id: str
    forecast_created_at: str
    live_detail: Literal["complete", "unavailable", "omitted"]
    payload: ArchiveObject


class ArchiveRun(BaseModel):
    run_id: str
    created_at: str
    archive_day: str
    payload: ArchiveObject


class ArchiveManifest(BaseModel):
    schema_hash: str
    archived_through: str
    archive_timezone: str = ARCHIVE_TIMEZONE
    days: list[ArchiveDay]
    runs: list[ArchiveRun]
    final_day: str
    default_route: str


class ArchivedResult(BaseModel):
    match: int
    date: str
    stage: str
    home_id: str | None = None
    away_id: str | None = None
    home_goals: int
    away_goals: int
    winner: str | None = None
    recorded_at: str


class ArchiveSidecars(BaseModel):
    distributions: DistributionsSidecar
    bracket_samples: BracketSamples
    pairing_matrices: PairingMatrices
    match_wdl_draws: MatchWdlDraws


class ArchiveRunRecord(BaseModel):
    run_id: str
    created_at: str
    status: Literal["completed", "failed"]
    cost: float | None = None
    duration_s: float | None = None
    kind: str


class FixtureMetadata(BaseModel):
    date: str
    stage: str


class ArchiveForecastPoint(BaseModel):
    run: RunMeta
    teams: list[TeamInfo]
    record: ArchiveRunRecord | None = None


class ArchiveDayPayload(BaseModel):
    schema_hash: str
    day: str
    cutoff_at: str
    selected_snapshot: Snapshot
    sidecars: ArchiveSidecars
    results: list[ArchivedResult] = Field(default_factory=list)
    forecast_history: list[ArchiveForecastPoint] = Field(default_factory=list)
    live_detail: Literal["complete", "unavailable", "omitted"] = "unavailable"


class ArchiveRunPayload(BaseModel):
    schema_hash: str
    snapshot: Snapshot
    distributions: DistributionsSidecar
    record: ArchiveRunRecord | None = None


class ArchiveAuditDay(BaseModel):
    day: str
    cutoff_at: str
    selected_run_id: str | None
    result_count: int | None
    live_detail: Literal["complete", "unavailable", "omitted"]
    source_keys: list[str] = Field(default_factory=list)
    error: str | None = None


class ArchiveAuditReport(BaseModel):
    days: list[ArchiveAuditDay]
    rejected_sources: dict[str, str] = Field(default_factory=dict)


def archive_schema_hash() -> str:
    """Return a content-derived identifier for the browser archive contract."""
    schemas = [
        ArchiveManifest.model_json_schema(),
        ArchiveDayPayload.model_json_schema(),
        ArchiveRunPayload.model_json_schema(),
    ]
    payload = json.dumps(schemas, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


ARCHIVE_SCHEMA_HASH = archive_schema_hash()
