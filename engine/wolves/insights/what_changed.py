"""The input-side diff: what is genuinely new since the previous run."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
from pydantic import BaseModel, Field

from wolves.agent.ledger import EvidenceLedger
from wolves.agent.source_memory import SourceMemory
from wolves.insights.market import moves_between
from wolves.sim.format import FormatData
from wolves.snapshot import Snapshot, run_day

if TYPE_CHECKING:
    from wolves.forecast import Forecaster

logger = logging.getLogger(__name__)

FIXTURE_WINDOW_HOURS = 48


class PlayedMatch(BaseModel):
    date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int

    def summary(self) -> str:
        return f"{self.home_team} {self.home_goals}-{self.away_goals} {self.away_team} ({self.date.isoformat()})"


class WhatChanged(BaseModel):
    previous_run_id: str | None = None
    previous_run_at: str | None = None
    title_moves_pp: dict[str, float] = Field(default_factory=dict)
    new_sources: list[str] = Field(default_factory=list)
    expired_evidence: list[str] = Field(default_factory=list)
    played_results: list[PlayedMatch] = Field(default_factory=list)
    market_moves_pp: dict[str, float] = Field(default_factory=dict)
    upcoming_fixtures: list[str] = Field(default_factory=list)

    def digest(self) -> str:
        if self.previous_run_id is None:
            return "No previous run to diff against."
        parts = [f"Previous run {self.previous_run_id} ({self.previous_run_at})."]
        if self.title_moves_pp:
            moves = ", ".join(f"{t} {d:+.1f}pp" for t, d in list(self.title_moves_pp.items())[:8])
            parts.append(f"Baseline title moves since then: {moves}.")
        if self.played_results:
            shown = "; ".join(m.summary() for m in self.played_results[:5])
            parts.append(f"{len(self.played_results)} result(s) played since: {shown}.")
        if self.market_moves_pp:
            moves = ", ".join(f"{t} {d:+.1f}pp" for t, d in list(self.market_moves_pp.items())[:8])
            parts.append(f"Market outright moves since then: {moves}.")
        if self.upcoming_fixtures:
            parts.append(
                f"{len(self.upcoming_fixtures)} fixture(s) within 48h: {'; '.join(self.upcoming_fixtures[:6])}."
            )
        if self.new_sources:
            parts.append(f"{len(self.new_sources)} source(s) never seen before this run.")
        if self.expired_evidence:
            parts.append(f"Evidence expired since: {', '.join(self.expired_evidence)}.")
        return " ".join(parts)


def played_since(dataset_path: Path, *, since: date, until: date) -> list[PlayedMatch]:
    """Full internationals in the research dataset played in [since, until], oldest first."""
    connection = duckdb.connect(str(dataset_path), read_only=True)
    try:
        rows = connection.execute(
            "select date, home_team, away_team, home_goals, away_goals from matches"
            " where date >= ? and date <= ? order by date, home_team",
            [since, until],
        ).fetchall()
    finally:
        connection.close()
    return [
        PlayedMatch(date=row[0], home_team=row[1], away_team=row[2], home_goals=row[3], away_goals=row[4])
        for row in rows
    ]


def fixtures_within(fmt: FormatData, *, on: date, hours: int = FIXTURE_WINDOW_HOURS) -> list[str]:
    """Fixtures kicking off within the window from the start of the run day."""
    start = datetime(on.year, on.month, on.day, tzinfo=UTC)
    end = start + timedelta(hours=hours)
    return [
        f"{match.home} vs {match.away} on {match.date[:10]}"
        for match in sorted([*fmt.group_matches, *fmt.knockout], key=lambda m: m.date)
        if start <= datetime.fromisoformat(match.date) < end
    ]


def diff_inputs(
    *,
    previous: Snapshot | None,
    forecaster: Forecaster | None,
    archive_dir: Path,
    as_of: str,
    move_floor_pp: float,
) -> tuple[list[PlayedMatch], dict[str, float], list[str]]:
    """Data-side diff inputs, each degrading to empty when its source is absent."""
    played: list[PlayedMatch] = []
    moves: dict[str, float] = {}
    fixtures: list[str] = []
    today = date.fromisoformat(as_of)
    if forecaster is not None:
        fixtures = fixtures_within(forecaster.fmt, on=today)
    if previous is None:
        return played, moves, fixtures
    if forecaster is not None:
        try:
            played = played_since(forecaster.dataset.path, since=date.fromisoformat(run_day(previous.run)), until=today)
        except Exception as exc:
            logger.warning("played-results diff skipped: %s", exc)
    moves = moves_between(archive_dir, since=previous.run.created_at, floor_pp=move_floor_pp)
    return played, moves, fixtures


def what_changed(
    *,
    previous: Snapshot | None,
    current_titles: dict[str, float] | None,
    ledger: EvidenceLedger,
    source_memory: SourceMemory | None,
    run_id: str,
    as_of: str,
    move_floor_pp: float = 0.3,
    played_results: list[PlayedMatch] | None = None,
    market_moves_pp: dict[str, float] | None = None,
    upcoming_fixtures: list[str] | None = None,
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
        played_results=played_results or [],
        market_moves_pp=market_moves_pp or {},
        upcoming_fixtures=upcoming_fixtures or [],
    )


def load_latest_snapshot(snapshot_dir: Path, *, before: date) -> Snapshot | None:
    from wolves.agent.scoring import load_previous_snapshots

    latest, _ = load_previous_snapshots(snapshot_dir, before=before)
    return latest
