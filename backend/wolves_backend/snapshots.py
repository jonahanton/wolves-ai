from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from wolves_backend.clients.snapshot_bucket import SnapshotBucket

RUN_ID_PATTERN = re.compile(r"^run-(\d{4})(\d{2})(\d{2})$")
LATEST_KEY = "snapshots/latest.json"


def is_valid_run_id(run_id: str) -> bool:
    return RUN_ID_PATTERN.fullmatch(run_id) is not None


class SnapshotSource:
    """Serve snapshot JSON from S3 when a bucket is configured, otherwise the
    local runs directory; both share one key space."""

    def __init__(self, *, bucket: SnapshotBucket | None, local_dir: Path) -> None:
        self._bucket = bucket
        self._local_dir = local_dir

    async def read(self, run_id: str) -> str | None:
        match = RUN_ID_PATTERN.fullmatch(run_id)
        if match is None:
            return None
        year, month, day = match.groups()
        return await self._read(f"snapshots/{year}/{month}/{day}/{run_id}.json")

    async def read_latest(self) -> str | None:
        return await self._read(LATEST_KEY)

    async def _read(self, key: str) -> str | None:
        if self._bucket is not None:
            return await asyncio.to_thread(self._bucket.get, key)
        try:
            return await asyncio.to_thread((self._local_dir / key).read_text, "utf-8")
        except OSError:
            return None
