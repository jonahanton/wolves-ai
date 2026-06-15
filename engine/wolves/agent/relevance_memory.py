from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path

from pydantic import BaseModel


class RankedSource(BaseModel):
    url: str
    sub_question: str
    score: float
    reason: str
    ranked_at: str
    run_id: str


class RelevanceMemory:
    """Cross-run memory of relevance judgements, so a source already scored
    arrives at the next ranking with its prior verdict and timestamp."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._latest: dict[str, RankedSource] = {}
        self._history: dict[str, list[RankedSource]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = RankedSource.model_validate_json(line)
                    self._history.setdefault(record.url, []).append(record)
                    self._latest[record.url] = record

    def latest(
        self, url: str, *, as_of: str | None = None, current_run_id: str | None = None
    ) -> RankedSource | None:
        if as_of is not None:
            return _latest_before(self._history.get(url, []), as_of, current_run_id=current_run_id)
        return self._latest.get(url)

    def recent(
        self, *, limit: int = 12, as_of: str | None = None, current_run_id: str | None = None
    ) -> list[RankedSource]:
        records = [
            _latest_before(history, as_of, current_run_id=current_run_id) for history in self._history.values()
        ]
        records = [record for record in records if record is not None]
        return sorted(records, key=lambda record: record.ranked_at, reverse=True)[:limit]

    def record(self, *, url: str, sub_question: str, score: float, reason: str, run_id: str) -> RankedSource:
        record = RankedSource(
            url=url,
            sub_question=sub_question,
            score=score,
            reason=reason,
            ranked_at=datetime.now(UTC).isoformat(timespec="seconds"),
            run_id=run_id,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
        self._history.setdefault(url, []).append(record)
        self._latest[url] = record
        return record


def _latest_before(
    records: list[RankedSource], as_of: str | None, *, current_run_id: str | None
) -> RankedSource | None:
    latest = _end_of_day(as_of)
    if latest is None:
        return records[-1] if records else None
    visible = [
        record
        for record in records
        if record.run_id == current_run_id or datetime.fromisoformat(record.ranked_at) <= latest
    ]
    return visible[-1] if visible else None


def _end_of_day(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(date.fromisoformat(value), time.max, tzinfo=UTC)
    except ValueError:
        return None
