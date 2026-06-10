"""Snapshot publication shared by the scheduled entrypoints: local files for
dev parity, S3 for the site, the run index for ops. Defence in depth on the
kill switch: the EventBridge schedule state is the primary switch and the
run_enabled control item is re-checked here so an in-flight schedule change
still stops the run. An unreachable table must not block local dev, so it
downgrades to a warning."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from wolves.store.records import RunRecord, RunStatus
from wolves.store.store import RunIndex, RunIndexUnavailableError, SnapshotStore

if TYPE_CHECKING:
    from datetime import date

    from wolves.config import Settings
    from wolves.snapshot import Snapshot

logger = logging.getLogger(__name__)


def build_run_index(settings: Settings) -> RunIndex | None:
    """Construct the run index when cloud config is present: a snapshot bucket
    (production) or an explicit local DynamoDB endpoint (dev stack)."""
    if not settings.snapshot_bucket and not settings.dynamo_endpoint:
        return None
    return RunIndex(
        table_name=settings.dynamo_table,
        region=settings.aws_region,
        endpoint_url=settings.dynamo_endpoint or None,
    )


def write_local_snapshot(settings: Settings, snapshot: Snapshot) -> None:
    """Write the dated snapshot file and repoint latest.json locally."""
    payload = snapshot.model_dump_json(indent=1)
    settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
    (settings.snapshot_dir / f"{snapshot.run.run_id}.json").write_text(payload)
    (settings.snapshot_dir / "latest.json").write_text(payload)


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

    def publish(self, snapshot: Snapshot, *, as_of: date, started: float) -> str:
        """Publish the snapshot everywhere configured; return the S3 key ('' locally)."""
        write_local_snapshot(self._settings, snapshot)
        s3_key = ""
        if self._settings.snapshot_bucket:
            store = SnapshotStore(bucket=self._settings.snapshot_bucket, region=self._settings.aws_region)
            s3_key = store.put_snapshot(snapshot, as_of=as_of)
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
