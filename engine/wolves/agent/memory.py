from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

_JOURNAL_NAME = "journal.md"


class RunMemory:
    """Dated append-only journals per run plus one curated LESSONS.md.

    The journal is the agent's working diary for a single run; LESSONS.md is
    the small cross-run file read in full at the start of every run."""

    def __init__(self, *, runs_root: Path, run_id: str, lessons_path: Path) -> None:
        self.runs_root = runs_root
        self.run_id = run_id
        self.lessons_path = lessons_path
        self.journal_path = runs_root / run_id / _JOURNAL_NAME

    def read_lessons(self) -> str:
        if not self.lessons_path.exists():
            return ""
        return self.lessons_path.read_text(encoding="utf-8")

    def append_lessons(self, text: str) -> None:
        if not text.strip():
            return
        self.lessons_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d")
        with self.lessons_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## {stamp} ({self.run_id})\n\n{text.strip()}\n")

    def write_journal(self, text: str) -> Path:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n### {stamp}\n\n{text.strip()}\n")
        return self.journal_path

    def read_journal(self, run_id: str) -> str | None:
        path = self.runs_root / run_id / _JOURNAL_NAME
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def read_latest_journal(self) -> str | None:
        """Return the most recent journal from a previous run, if any."""
        candidates = sorted(
            (p for p in self.runs_root.glob(f"*/{_JOURNAL_NAME}") if p.parent.name != self.run_id),
            key=lambda p: p.parent.name,
        )
        if not candidates:
            return None
        return candidates[-1].read_text(encoding="utf-8")
