"""The input-side diff: what is genuinely new since the previous run."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from wolves.agent.ledger import EvidenceLedger
from wolves.agent.source_memory import SourceMemory
from wolves.snapshot import Snapshot, run_day


class WhatChanged(BaseModel):
    previous_run_id: str | None = None
    previous_run_at: str | None = None
    title_moves_pp: dict[str, float] = Field(default_factory=dict)
    new_sources: list[str] = Field(default_factory=list)
    expired_evidence: list[str] = Field(default_factory=list)

    def digest(self) -> str:
        if self.previous_run_id is None:
            return "No previous run to diff against."
        parts = [f"Previous run {self.previous_run_id} ({self.previous_run_at})."]
        if self.title_moves_pp:
            moves = ", ".join(f"{t} {d:+.1f}pp" for t, d in list(self.title_moves_pp.items())[:8])
            parts.append(f"Baseline title moves since then: {moves}.")
        if self.new_sources:
            parts.append(f"{len(self.new_sources)} source(s) never seen before this run.")
        if self.expired_evidence:
            parts.append(f"Evidence expired since: {', '.join(self.expired_evidence)}.")
        return " ".join(parts)


def what_changed(
    *,
    previous: Snapshot | None,
    current_titles: dict[str, float] | None,
    ledger: EvidenceLedger,
    source_memory: SourceMemory | None,
    run_id: str,
    as_of: str,
    move_floor_pp: float = 0.3,
) -> WhatChanged:
    if previous is None:
        return WhatChanged()
    moves: dict[str, float] = {}
    if current_titles is not None:
        previous_titles = {t.team_id: t.champion_prob for t in previous.teams}
        deltas = {
            team: (p - previous_titles.get(team, 0.0)) * 100
            for team, p in current_titles.items()
            if abs(p - previous_titles.get(team, 0.0)) * 100 >= move_floor_pp
        }
        moves = dict(sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True))
    today = date.fromisoformat(as_of)
    previous_day = date.fromisoformat(run_day(previous.run))
    expired = [
        e.id for e in ledger.all() if e.expiry is not None and previous_day <= date.fromisoformat(e.expiry) < today
    ]
    new_sources = [r.url for r in source_memory.new_since(run_id)] if source_memory is not None else []
    return WhatChanged(
        previous_run_id=previous.run.run_id,
        previous_run_at=previous.run.created_at,
        title_moves_pp=moves,
        new_sources=new_sources,
        expired_evidence=expired,
    )


def load_latest_snapshot(snapshot_dir: Path, *, before: date) -> Snapshot | None:
    from wolves.agent.scoring import load_previous_snapshots

    latest, _ = load_previous_snapshots(snapshot_dir, before=before)
    return latest
