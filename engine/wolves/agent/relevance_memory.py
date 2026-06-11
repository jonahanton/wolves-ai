from __future__ import annotations

from datetime import UTC, datetime
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
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    record = RankedSource.model_validate_json(line)
                    self._latest[record.url] = record

    def latest(self, url: str) -> RankedSource | None:
        return self._latest.get(url)

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
        self._latest[url] = record
        return record
