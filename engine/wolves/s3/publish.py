"""Snapshot publication, re-checking the kill switch; an unreachable index degrades to a warning."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from wolves.s3.artifacts import ArtifactStore
from wolves.s3.index import RunIndex, RunIndexUnavailableError
from wolves.s3.layout import SNAPSHOT_SIDECAR
from wolves.s3.records import RunRecord, RunStatus
from wolves.s3.snapshots import SnapshotStore
from wolves.sidecars import SIDECAR_NAMES, UnknownSidecarError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date

    from pydantic import BaseModel

    from wolves.config import Settings
    from wolves.snapshot import Snapshot

logger = logging.getLogger(__name__)


def build_run_index(settings: Settings) -> RunIndex | None:
    """Construct the run index when cloud config is present: cloud storage on
    (production) or an explicit local DynamoDB endpoint (dev stack)."""
    if settings.storage_mode == "local" and not settings.dynamo_endpoint:
        return None
    return RunIndex(
        table_name=settings.dynamo_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamo_endpoint or None,
    )


class SnapshotPublisher:
    """Kill-switch check plus local, S3 and run-index publication."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index = build_run_index(settings)

    def run_enabled(self) -> bool:
        if self._index is None:
            return True
        try:
            return self._index.run_enabled()
        except RunIndexUnavailableError:
            logger.warning("run index unreachable; proceeding as enabled")
            return True

    def publish(
        self,
        snapshot: Snapshot,
        *,
        as_of: date,
        started: float,
        sidecars: Mapping[str, BaseModel] | None = None,
    ) -> str:
        """Publish the snapshot everywhere configured; return the dated key."""
        artifacts = ArtifactStore(self._settings)
        store = SnapshotStore(artifacts)
        s3_key = store.put_snapshot(snapshot, as_of=as_of)
        for name, payload in (sidecars or {}).items():
            if name not in SIDECAR_NAMES:
                raise UnknownSidecarError(name)
            artifacts.put(
                SNAPSHOT_SIDECAR,
                payload.model_dump_json(),
                date=f"{as_of:%Y/%m/%d}",
                run_id=snapshot.run.run_id,
                dataset=name,
            )
        self._record(
            run_id=snapshot.run.run_id,
            created_at=snapshot.run.created_at,
            s3_key=s3_key,
            status="completed",
            started=started,
            kind=snapshot.run.kind,
        )
        return s3_key

    def record_failure(self, *, run_id: str, created_at: str, started: float) -> None:
        self._record(run_id=run_id, created_at=created_at, s3_key="", status="failed", started=started, kind="")

    def _record(
        self,
        *,
        run_id: str,
        created_at: str,
        s3_key: str,
        status: RunStatus,
        started: float,
        kind: str,
    ) -> None:
        if self._index is None:
            return
        record = RunRecord(
            run_id=run_id,
            created_at=created_at,
            s3_key=s3_key,
            status=status,
            cost=0.0,
            duration_s=round(time.monotonic() - started, 3),
            kind=kind or "sim_only",
        )
        try:
            self._index.record_run(record)
        except RunIndexUnavailableError:
            logger.warning("run index unreachable; %s not indexed", run_id)
