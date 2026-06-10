"""Everything the dataset and the fitted model know about one team, in one call."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wolves.data.query import DatasetQuery
from wolves.data.teams import registry_team_key
from wolves.forecast import Forecaster
from wolves.insights.explain import StrengthExplanation, model_explain
from wolves.markets.devig import power_devig
from wolves.markets.series import load_series
from wolves.sim.outputs import build_team_reach

HISTORY_TOURNAMENTS = 2


class UnknownTeamError(Exception):
    def __init__(self, team: str, known: list[str]) -> None:
        self.team = team
        self.known = known
        super().__init__(f"unknown team {team!r}; valid ids include {known[:6]}")


class UpcomingFixture(BaseModel):
    match: int
    date: str
    opponent: str
    city: str


class HistoricalClose(BaseModel):
    """One tournament match summarised to its consensus de-vigged probability."""

    tournament: str
    commence_at: str
    opponent: str
    venue_side: str
    p_win: float
    p_draw: float
    p_lose: float
    bookmakers: int


class TeamDossier(BaseModel):
    team: str
    group: str
    upcoming: list[UpcomingFixture]
    model_reach: dict[str, float]
    market_outright_now: float | None
    polymarket_outright_now: float | None
    explanation: StrengthExplanation
    recent_form: list[dict[str, Any]]
    market_history: list[HistoricalClose]
    outright_history: list[dict[str, Any]]


def _consensus_closes(rows: list[dict[str, Any]], key: str) -> list[HistoricalClose]:
    by_match: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        by_match.setdefault((row["tournament"], row["commence_at"]), []).append(row)
    tournaments = sorted({t for t, _ in by_match}, reverse=True)[:HISTORY_TOURNAMENTS]
    closes = []
    for (tournament, commence), entries in sorted(by_match.items()):
        if tournament not in tournaments:
            continue
        we_are_home = entries[0]["home_team"] == key
        probs = [power_devig([float(e["home_price"]), float(e["draw_price"]), float(e["away_price"])]) for e in entries]
        p_home = statistics.median(p[0] for p in probs)
        p_draw = statistics.median(p[1] for p in probs)
        p_away = statistics.median(p[2] for p in probs)
        total = p_home + p_draw + p_away
        closes.append(
            HistoricalClose(
                tournament=tournament,
                commence_at=str(commence),
                opponent=entries[0]["away_team"] if we_are_home else entries[0]["home_team"],
                venue_side="home" if we_are_home else "away",
                p_win=round((p_home if we_are_home else p_away) / total, 4),
                p_draw=round(p_draw / total, 4),
                p_lose=round((p_away if we_are_home else p_home) / total, 4),
                bookmakers=len(entries),
            )
        )
    return closes


def team_dossier(
    forecaster: Forecaster, team: str, *, form_matches: int = 12, archive_dir: Path | None = None
) -> TeamDossier:
    key = registry_team_key(team)
    spec = next((t for t in forecaster.fmt.teams if t.id == team), None)
    if spec is None:
        raise UnknownTeamError(team, [t.id for t in forecaster.fmt.teams])
    upcoming = [
        UpcomingFixture(
            match=m.match,
            date=m.date,
            opponent=m.away if m.home == team else m.home,
            city=m.city,
        )
        for m in forecaster.fmt.group_matches
        if team in (m.home, m.away)
    ]
    reach = build_team_reach(forecaster.fmt, forecaster.simulate(n_sims=20_000, seed=0, parameter_uncertainty=False))[
        team
    ]

    market_now = polymarket_now = None
    if archive_dir is not None:
        series = load_series(archive_dir)
        if series:
            market_now = series[-1].outright_bookmakers.get(team)
            polymarket_now = series[-1].outright_polymarket.get(team)

    with DatasetQuery(forecaster.dataset) as query:
        form = query.team_form(key, last=form_matches)
        market = query.market_history(key)
        outrights = query.outright_history(key)
    return TeamDossier(
        team=team,
        group=spec.group,
        upcoming=sorted(upcoming, key=lambda f: f.date),
        model_reach=reach,
        market_outright_now=market_now,
        polymarket_outright_now=polymarket_now,
        explanation=model_explain(forecaster, team),
        recent_form=form,
        market_history=_consensus_closes(market, key),
        outright_history=outrights,
    )
