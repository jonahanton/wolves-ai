from __future__ import annotations

import re
from typing import TYPE_CHECKING

from wolves_backend.models import SnapshotRef

if TYPE_CHECKING:
    from datetime import date

    from wolves_backend.storage import Storage

RUN_ID_PATTERN = re.compile(r"^(run|live|agent)-(\d{4})(\d{2})(\d{2})(?:-\d{6})?$")
SNAPSHOT_KEY_PATTERN = re.compile(r"^snapshots/(\d{4})/(\d{2})/(\d{2})/((run|live|agent)-\d{8}(?:-\d{6})?)\.json$")
DISTRIBUTIONS_KEY_PATTERN = re.compile(
    r"^snapshots/\d{4}/\d{2}/\d{2}/((run|live|agent)-\d{8}(?:-\d{6})?)\.distributions\.json$"
)
LATEST_KEY = "snapshots/latest.json"
SNAPSHOTS_PREFIX = "snapshots/"


def is_valid_run_id(run_id: str) -> bool:
    return RUN_ID_PATTERN.fullmatch(run_id) is not None


def snapshot_refs(keys: list[str]) -> list[SnapshotRef]:
    """Parse listed snapshot keys into refs, newest first."""
    with_distributions = {
        match.group(1) for key in keys if (match := DISTRIBUTIONS_KEY_PATTERN.fullmatch(key)) is not None
    }
    refs = []
    for key in keys:
        match = SNAPSHOT_KEY_PATTERN.fullmatch(key)
        if match is None:
            continue
        year, month, day, run_id, kind = match.groups()
        refs.append(
            SnapshotRef(
                run_id=run_id,
                as_of=f"{year}-{month}-{day}",
                kind=kind,
                key=key,
                has_distributions=run_id in with_distributions,
            )
        )
    refs.sort(key=lambda ref: (ref.as_of, ref.run_id), reverse=True)
    return refs


class SnapshotSource:
    """Published snapshot reads over the shared storage key space."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def read(self, run_id: str) -> str | None:
        match = RUN_ID_PATTERN.fullmatch(run_id)
        if match is None:
            return None
        _, year, month, day = match.groups()
        return await self._storage.read(f"snapshots/{year}/{month}/{day}/{run_id}.json")

    async def read_sidecar(self, run_id: str, dataset: str) -> str | None:
        match = RUN_ID_PATTERN.fullmatch(run_id)
        if match is None:
            return None
        _, year, month, day = match.groups()
        return await self._storage.read(f"snapshots/{year}/{month}/{day}/{run_id}.{dataset}.json")

    async def read_latest(self) -> str | None:
        return await self._storage.read(LATEST_KEY)

    async def index(self) -> list[SnapshotRef]:
        return snapshot_refs(await self._storage.list_keys(SNAPSHOTS_PREFIX))

    async def index_for(self, day: date) -> list[SnapshotRef]:
        return snapshot_refs(await self._storage.list_keys(f"{SNAPSHOTS_PREFIX}{day:%Y/%m/%d}/"))
