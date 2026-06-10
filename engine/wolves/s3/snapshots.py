"""Snapshot writes: an immutable dated key per run plus the latest pointer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from wolves.s3.layout import SNAPSHOT, SNAPSHOT_LATEST
from wolves.snapshot import Snapshot

if TYPE_CHECKING:
    from datetime import date

    from wolves.s3.artifacts import ArtifactStore


def snapshot_key(as_of: date, run_id: str) -> str:
    return SNAPSHOT.key(date=f"{as_of:%Y/%m/%d}", run_id=run_id)


class SnapshotStore:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def put_snapshot(self, snapshot: Snapshot, *, as_of: date) -> str:
        """Persist the snapshot and repoint the latest copy; return the dated key."""
        body = snapshot.model_dump_json()
        key = self._artifacts.put(SNAPSHOT, body, date=f"{as_of:%Y/%m/%d}", run_id=snapshot.run.run_id)
        if self._newer_than_latest(snapshot):
            self._artifacts.put(SNAPSHOT_LATEST, body)
        return key

    def _newer_than_latest(self, snapshot: Snapshot) -> bool:
        # Concurrent daily and live runs race on the pointer; the older
        # snapshot must not win. A narrow read-then-write window remains,
        # acceptable at this run cadence.
        current = self._artifacts.get(SNAPSHOT_LATEST)
        if current is None:
            return True
        try:
            existing = Snapshot.model_validate_json(current)
        except ValidationError:
            return True
        return snapshot.run.created_at >= existing.run.created_at
