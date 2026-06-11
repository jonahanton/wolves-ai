from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from wolves.agent.contracts import LedgerStatus
from wolves.agent.sources import source_tier


class LedgerEntry(BaseModel):
    id: str
    claim: str
    source_url: str
    status: LedgerStatus
    mechanism: str
    proposed_delta: float = 0.0
    expiry: str | None = None
    team_id: str | None = None
    relevance: float | None = None
    source_tier: int | None = None
    retrieved_at: str | None = None
    retrieval_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceLedger:
    """Append-only JSONL evidence ledger for one run. Existing entries are
    loaded on construction so a resumed run keeps its ids monotonic."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[LedgerEntry] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._entries.append(LedgerEntry.model_validate_json(line))

    def append(
        self,
        *,
        claim: str,
        source_url: str,
        status: LedgerStatus,
        mechanism: str,
        proposed_delta: float = 0.0,
        expiry: str | None = None,
        team_id: str | None = None,
        relevance: float | None = None,
        retrieval_id: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            id=f"led-{len(self._entries) + 1:04d}",
            claim=claim,
            source_url=source_url,
            status=status,
            mechanism=mechanism,
            proposed_delta=proposed_delta,
            expiry=expiry,
            team_id=team_id,
            relevance=relevance,
            source_tier=source_tier(source_url),
            retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
            retrieval_id=retrieval_id,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")
        self._entries.append(entry)
        return entry

    def get(self, entry_id: str) -> LedgerEntry | None:
        return next((e for e in self._entries if e.id == entry_id), None)

    def query(
        self,
        *,
        team_id: str | None = None,
        status: LedgerStatus | None = None,
        fresh_on: date | None = None,
    ) -> list[LedgerEntry]:
        """Filter entries; `fresh_on` keeps entries unexpired on that date."""
        out = self._entries
        if team_id is not None:
            out = [e for e in out if e.team_id == team_id]
        if status is not None:
            out = [e for e in out if e.status == status]
        if fresh_on is not None:
            out = [e for e in out if e.expiry is None or date.fromisoformat(e.expiry) >= fresh_on]
        return list(out)

    def all(self) -> list[LedgerEntry]:
        return list(self._entries)
