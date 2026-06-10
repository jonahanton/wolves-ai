from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

_JOURNAL_NAME = "journal.md"
LESSONS_SHOWN = 25


class Lesson(BaseModel):
    date: str
    run_id: str
    scope: str
    text: str


def run_dir(runs_root: Path, run_id: str) -> Path:
    """Per-run artifact directory; runs/ nests under the mirror root so the
    local tree matches the bucket key space exactly."""
    return runs_root / "runs" / run_id


class RunMemory:
    """Dated append-only journal per run plus structured cross-run lessons."""

    def __init__(self, *, runs_root: Path, run_id: str, lessons_path: Path) -> None:
        self.runs_root = runs_root
        self.run_id = run_id
        self.lessons_path = lessons_path
        self.journal_path = run_dir(runs_root, run_id) / _JOURNAL_NAME

    def read_lessons(self) -> str:
        """The most recent lessons formatted for a prompt, newest last."""
        if not self.lessons_path.exists():
            return ""
        lines = self.lessons_path.read_text(encoding="utf-8").splitlines()
        lessons = [Lesson.model_validate_json(line) for line in lines if line.strip()]
        return "\n".join(f"- [{x.date} {x.scope}] {x.text}" for x in lessons[-LESSONS_SHOWN:])

    def append_lessons(self, text: str, *, scope: str = "general") -> None:
        if not text.strip():
            return
        self.lessons_path.parent.mkdir(parents=True, exist_ok=True)
        lesson = Lesson(
            date=datetime.now(UTC).strftime("%Y-%m-%d"), run_id=self.run_id, scope=scope, text=text.strip()
        )
        with self.lessons_path.open("a", encoding="utf-8") as handle:
            handle.write(lesson.model_dump_json() + "\n")

    def write_journal(self, text: str) -> Path:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n### {stamp}\n\n{text.strip()}\n")
        return self.journal_path

    def read_journal(self, run_id: str) -> str | None:
        path = run_dir(self.runs_root, run_id) / _JOURNAL_NAME
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def read_latest_journal(self) -> str | None:
        """Return the most recent journal from a previous run, if any."""
        candidates = sorted(
            (
                p
                for p in (self.runs_root / "runs").glob(f"*/{_JOURNAL_NAME}")
                if p.parent.name != self.run_id
            ),
            key=lambda p: p.parent.name,
        )
        if not candidates:
            return None
        return candidates[-1].read_text(encoding="utf-8")
