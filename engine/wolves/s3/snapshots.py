"""Snapshot writes: an immutable dated key per run plus the latest pointer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wolves.s3.layout import SNAPSHOT, SNAPSHOT_LATEST

if TYPE_CHECKING:
    from datetime import date

    from wolves.s3.artifacts import ArtifactStore
    from wolves.snapshot import Snapshot


def snapshot_key(as_of: date, run_id: str) -> str:
    return SNAPSHOT.key(date=f"{as_of:%Y/%m/%d}", run_id=run_id)


class SnapshotStore:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def put_snapshot(self, snapshot: Snapshot, *, as_of: date) -> str:
        """Persist the snapshot and repoint the latest copy; return the dated key."""
        body = snapshot.model_dump_json()
        key = self._artifacts.put(SNAPSHOT, body, date=f"{as_of:%Y/%m/%d}", run_id=snapshot.run.run_id)
        self._artifacts.put(SNAPSHOT_LATEST, body)
        return key
