"""Canonical blob layout; every artifact family is one ArtifactSpec entry."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

BUCKET_DEV = "wolves-superforecaster-dev"
BUCKET_PROD = "wolves-superforecaster-prod"

StorageMode = Literal["local", "s3", "both"]

JSON = "application/json"
NDJSON = "application/x-ndjson"
MARKDOWN = "text/markdown; charset=utf-8"
BINARY = "application/octet-stream"


class UnknownArtifactError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"no artifact named {name!r} in the layout")


class ArtifactSpec(BaseModel):
    """One artifact family: its key pattern, content type and read semantics."""

    model_config = ConfigDict(frozen=True)

    name: str
    pattern: str
    content_type: str = JSON
    mutable: bool = False
    description: str

    @property
    def prefix(self) -> str:
        """The directory prefix the family lives under, for listing and syncing."""
        head = self.pattern.split("{", 1)[0]
        return head[: head.rfind("/") + 1]

    @property
    def prefer(self) -> Literal["local", "s3"]:
        # A mutable pointer may be repointed by another environment, so the bucket is authoritative.
        return "s3" if self.mutable else "local"

    def key(self, **parts: str) -> str:
        return self.pattern.format(**parts)


SNAPSHOT = ArtifactSpec(
    name="snapshot",
    pattern="snapshots/{date}/{run_id}.json",
    description="Published forecast snapshot, immutable per run; date is YYYY/MM/DD.",
)
SNAPSHOT_LATEST = ArtifactSpec(
    name="snapshot-latest",
    pattern="snapshots/latest.json",
    mutable=True,
    description="Full copy of the most recently published snapshot.",
)
RUN_JOURNAL = ArtifactSpec(
    name="run-journal",
    pattern="runs/{run_id}/journal.md",
    content_type=MARKDOWN,
    description="Agent journal appended during one run.",
)
RUN_ARTIFACT = ArtifactSpec(
    name="run-artifact",
    pattern="runs/{run_id}/artifacts/{artifact_id}.json",
    description="One node-produced artifact: typed payload plus metadata.",
)
RUN_ARTIFACT_INDEX = ArtifactSpec(
    name="run-artifact-index",
    pattern="runs/{run_id}/artifacts/index.json",
    mutable=True,
    description="Metadata index over one run's artifacts; rewritten as the run grows.",
)
RUN_EVENTS = ArtifactSpec(
    name="run-events",
    pattern="runs/{run_id}/events.jsonl",
    content_type=NDJSON,
    description="Append-only event log for one run.",
)
RUN_WORKSPACE_FILE = ArtifactSpec(
    name="run-workspace-file",
    pattern="runs/{run_id}/workspace/{path}",
    content_type=BINARY,
    description="One file from a run's working tree (quant code, inputs, outputs).",
)
DATASET = ArtifactSpec(
    name="dataset",
    pattern="datasets/wolves-data-{dataset_id}.duckdb",
    content_type=BINARY,
    description="Research DuckDB; the id is a digest of the source hashes.",
)
DATASET_MANIFEST = ArtifactSpec(
    name="dataset-manifest",
    pattern="datasets/wolves-data-{dataset_id}.duckdb.manifest.json",
    description="Tables, row counts and source hashes for one dataset.",
)
DATASET_LATEST = ArtifactSpec(
    name="dataset-latest",
    pattern="datasets/latest.json",
    mutable=True,
    description="Pointer to the dataset id runs should fit on unless they pin one.",
)
CHAMPION = ArtifactSpec(
    name="champion",
    pattern="models/champion.json",
    mutable=True,
    description="The gate-promoted model record that produces published numbers.",
)
ODDS_SNAPSHOT = ArtifactSpec(
    name="odds-snapshot",
    pattern="odds-archive/{date}/{time}.json",
    description="Raw odds and Polymarket payloads exactly as the APIs returned them.",
)
ODDS_SERIES_POINT = ArtifactSpec(
    name="odds-series-point",
    pattern="odds-archive/{date}/{time}.series.json",
    description="Parsed market probabilities for one snapshot; rebuildable from raw.",
)
ODDS_CLOSE = ArtifactSpec(
    name="odds-close",
    pattern="odds-archive/closes/{tournament}/{snapshot}.json",
    description="Purchased historical closing odds backing the gate holdout.",
)
RESULTS = ArtifactSpec(
    name="results",
    pattern="live/results.json",
    mutable=True,
    description="Played results and finished fixtures persisted from live polling; merged on write.",
)
LESSONS = ArtifactSpec(
    name="lessons",
    pattern="agent-state/lessons.jsonl",
    content_type=NDJSON,
    mutable=True,
    description="Append-only cross-run agent lessons.",
)
SCENARIOS = ArtifactSpec(
    name="scenarios",
    pattern="agent-state/scenarios.jsonl",
    content_type=NDJSON,
    mutable=True,
    description="Cross-run scenario registry: lifecycle status and weight history per scenario id.",
)
SOURCES_SEEN = ArtifactSpec(
    name="sources-seen",
    pattern="agent-state/sources_seen.jsonl",
    content_type=NDJSON,
    mutable=True,
    description="Cross-run memory of sources already fetched, for dedupe and what_changed.",
)
RELEVANCE_FEEDBACK = ArtifactSpec(
    name="relevance-feedback",
    pattern="agent-state/relevance_feedback.jsonl",
    content_type=NDJSON,
    mutable=True,
    description="Relevance scores joined with eventual ledger citation, for tier calibration.",
)
CALIBRATION = ArtifactSpec(
    name="calibration",
    pattern="agent-state/calibration.jsonl",
    content_type=NDJSON,
    mutable=True,
    description="Append-only ledger of per-match scores for landed forecasts.",
)

LAYOUT: tuple[ArtifactSpec, ...] = (
    SNAPSHOT,
    SNAPSHOT_LATEST,
    RUN_JOURNAL,
    RUN_ARTIFACT,
    RUN_ARTIFACT_INDEX,
    RUN_EVENTS,
    RUN_WORKSPACE_FILE,
    DATASET,
    DATASET_MANIFEST,
    DATASET_LATEST,
    CHAMPION,
    ODDS_SNAPSHOT,
    ODDS_SERIES_POINT,
    ODDS_CLOSE,
    RESULTS,
    LESSONS,
    SCENARIOS,
    SOURCES_SEEN,
    RELEVANCE_FEEDBACK,
    CALIBRATION,
)


def artifact(name: str) -> ArtifactSpec:
    for spec in LAYOUT:
        if spec.name == name:
            return spec
    raise UnknownArtifactError(name)


def run_dir(runs_root: Path, run_id: str) -> Path:
    """Local directory mirroring the runs/{run_id}/ key prefix."""
    return runs_root / "runs" / run_id


def describe() -> str:
    """The layout as text, for humans and the agent."""
    lines = []
    for spec in LAYOUT:
        flags = ", mutable pointer" if spec.mutable else ""
        lines.append(f"{spec.pattern}  [{spec.content_type}{flags}]")
        lines.append(f"    {spec.description}")
    return "\n".join(lines)
