from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class SeenSource(BaseModel):
    url_hash: str
    url: str
    first_seen_run: str
    last_seen_run: str
    last_seen_at: str
    disposition: str


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


class SourceMemory:
    """Cross-run memory of sources already considered, so today's run can
    skip refetching yesterday's articles and report genuinely new ones."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._seen: dict[str, SeenSource] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = SeenSource.model_validate_json(line)
                    self._seen[record.url_hash] = record

    def seen(self, url: str) -> SeenSource | None:
        return self._seen.get(_url_hash(url))

    def record(self, url: str, *, run_id: str, disposition: str) -> SeenSource:
        """Idempotent within a run; the file stays append-only and the index
        keeps the latest record per url."""
        key = _url_hash(url)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        existing = self._seen.get(key)
        record = SeenSource(
            url_hash=key,
            url=url,
            first_seen_run=existing.first_seen_run if existing else run_id,
            last_seen_run=run_id,
            last_seen_at=now,
            disposition=disposition,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
        self._seen[key] = record
        return record

    def new_since(self, run_id: str) -> list[SeenSource]:
        return [r for r in self._seen.values() if r.first_seen_run == run_id]
