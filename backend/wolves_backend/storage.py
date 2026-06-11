from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from wolves_backend.clients.bucket import Bucket


class Storage:
    """One key space mirroring the engine's blob layout, served from S3 when a
    bucket is configured, otherwise the local runs directory."""

    def __init__(self, *, bucket: Bucket | None, local_dir: Path) -> None:
        self._bucket = bucket
        self._local_dir = local_dir

    async def read(self, key: str) -> str | None:
        if self._bucket is not None:
            return await asyncio.to_thread(self._bucket.get, key)
        try:
            return await asyncio.to_thread((self._local_dir / key).read_text, "utf-8")
        except OSError:
            return None

    async def list_keys(self, prefix: str) -> list[str]:
        if self._bucket is not None:
            return await asyncio.to_thread(self._bucket.list_keys, prefix)
        return await asyncio.to_thread(self._list_local, prefix)

    def _list_local(self, prefix: str) -> list[str]:
        base = self._local_dir / prefix
        if not base.is_dir():
            return []
        return sorted(path.relative_to(self._local_dir).as_posix() for path in base.rglob("*") if path.is_file())
