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


# A thin sim_only snapshot must never displace a richer agent or live one;
# agent and live share a tier so a live refit still supersedes on recency.
_LATEST_RANK = {"sim_only": 0, "live": 1, "agent": 1}


def _latest_rank(kind: str) -> int:
    return _LATEST_RANK.get(kind, 1)


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
        # Narrow read-then-write window on the pointer, acceptable at this cadence.
        current = self._artifacts.get(SNAPSHOT_LATEST)
        if current is None:
            return True
        try:
            existing = Snapshot.model_validate_json(current)
        except ValidationError:
            return True
        rank = _latest_rank(snapshot.run.kind)
        existing_rank = _latest_rank(existing.run.kind)
        if rank != existing_rank:
            return rank > existing_rank
        return snapshot.run.created_at >= existing.run.created_at
