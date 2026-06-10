"""Everything the dataset and the fitted model know about one team, in one call."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.data.query import DatasetQuery
from wolves.data.teams import registry_team_key
from wolves.forecast import Forecaster
from wolves.insights.explain import StrengthExplanation, model_explain


class UpcomingFixture(BaseModel):
    match: int
    date: str
    opponent: str
    city: str


class TeamDossier(BaseModel):
    team: str
    group: str
    upcoming: list[UpcomingFixture]
    explanation: StrengthExplanation
    recent_form: list[dict[str, Any]]
    market_history: list[dict[str, Any]]
    outright_history: list[dict[str, Any]]


def team_dossier(forecaster: Forecaster, team: str, *, form_matches: int = 12) -> TeamDossier:
    key = registry_team_key(team)
    spec = next(t for t in forecaster.fmt.teams if t.id == team)
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
    with DatasetQuery(forecaster.dataset) as query:
        form = query.team_form(key, last=form_matches)
        market = query.market_history(key)
        outrights = query.outright_history(key)
    return TeamDossier(
        team=team,
        group=spec.group,
        upcoming=sorted(upcoming, key=lambda f: f.date),
        explanation=model_explain(forecaster, team),
        recent_form=[{k: str(v) for k, v in row.items()} for row in form],
        market_history=[{k: str(v) for k, v in row.items()} for row in market],
        outright_history=[{k: str(v) for k, v in row.items()} for row in outrights],
    )
