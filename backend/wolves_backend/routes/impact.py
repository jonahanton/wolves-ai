"""Estimated movement of the agent's published forecast, measured by the engine.

Results on the run's own as_of date count as new: agent runs publish in the
morning, before that day's kickoffs.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from wolves.live_state import LiveFixture, LiveState
from wolves.s3.layout import LIVE_STATE
from wolves_backend.deps import Deps, get_deps
from wolves_backend.impact import estimated_stages, stage_impacts
from wolves_backend.live_history import day_states
from wolves_backend.models import Impact
from wolves_backend.sim import Pin

router = APIRouter()

DepsDep = Annotated[Deps, Depends(get_deps)]

MAX_TEAMS = 12
MAX_SERIES_POINTS = 120


def _held_pins(fixtures: list[LiveFixture]) -> tuple[Pin, ...]:
    return tuple(
        Pin(match=f.match, home_goals=f.home_goals, away_goals=f.away_goals)
        for f in fixtures
        if f.status == "live" and f.match is not None and f.home_goals is not None and f.away_goals is not None
    )


def _pin_key(pins: tuple[Pin, ...]) -> tuple[tuple[int, int, int], ...]:
    return tuple(sorted((p.match, p.home_goals, p.away_goals) for p in pins))


def _fixture_block(fixture: LiveFixture) -> dict[str, Any]:
    forecast = fixture.forecast
    return {
        "match": fixture.match,
        "home_id": fixture.home_id,
        "away_id": fixture.away_id,
        "home_name": fixture.home_name,
        "away_name": fixture.away_name,
        "home_goals": fixture.home_goals,
        "away_goals": fixture.away_goals,
        "minute": fixture.minute,
        "status": fixture.status,
        "p_home": forecast.p_home if forecast else None,
        "p_draw": forecast.p_draw if forecast else None,
        "p_away": forecast.p_away if forecast else None,
    }


def _selected_teams(
    requested: str | None, agent_reach: dict[str, dict[str, float]], in_play: list[LiveFixture], focus: str
) -> list[str]:
    if requested:
        names = [team.strip() for team in requested.split(",") if team.strip()]
        unknown = sorted(set(names) - set(agent_reach))
        if unknown:
            raise HTTPException(status_code=404, detail=f"no agent forecast for team(s) {', '.join(unknown)}")
        return names[:MAX_TEAMS]
    teams = [team for f in in_play for team in (f.home_id, f.away_id) if team is not None]
    if focus not in teams:
        teams.append(focus)
    by_champion = sorted(agent_reach, key=lambda team: -agent_reach[team].get("champion", 0.0))
    teams.extend(team for team in by_champion[:4] if team not in teams)
    return [team for team in teams if team in agent_reach][:MAX_TEAMS]


@router.get("/impact")
async def impact(deps: DepsDep, teams: Annotated[str | None, Query()] = None) -> Impact:
    refs = await deps.snapshots.index()
    agent_ref = next((ref for ref in refs if ref.kind == "agent"), None)
    body = await deps.storage.read(agent_ref.key) if agent_ref else None
    if body is None:
        raise HTTPException(status_code=404, detail="no agent forecast published")
    snapshot = json.loads(body)
    agent_reach = {t["team_id"]: t["reach_probs"] for t in snapshot["teams"] if t.get("reach_probs")}
    run = snapshot["run"]
    as_of = run.get("as_of") or run["created_at"][:10]
    results_until = (date.fromisoformat(as_of) - timedelta(days=1)).isoformat()

    live = await _live_state(deps)
    in_play = [f for f in live.fixtures if f.status == "live"] if live else []
    held = _held_pins(in_play)
    selected = _selected_teams(teams, agent_reach, in_play, snapshot["focus"]["team_id"])

    today = datetime.now(UTC).date().isoformat()
    states = await day_states(deps.storage, today, bound=MAX_SERIES_POINTS)
    legs: dict[str, tuple[tuple[Pin, ...], str | None]] = {
        "then": ((), results_until),
        "now": ((), None),
        "held": (held, None),
    }
    point_leg: list[str] = []
    leg_by_pins: dict[tuple[tuple[int, int, int], ...], str] = {}
    for state in states:
        pins = _held_pins([f for f in state.fixtures if f.status == "live"])
        key = _pin_key(pins)
        name = leg_by_pins.get(key)
        if name is None:
            name = f"s{len(leg_by_pins)}"
            leg_by_pins[key] = name
            legs[name] = (pins, None)
        point_leg.append(name)

    n_sims = deps.engine.settings.n_sims
    result = await deps.engine.reach_legs(legs, n_sims=n_sims)
    then, now, held_reach = result["legs"]["then"], result["legs"]["now"], result["legs"]["held"]

    payload = {
        "agent_run_id": run["run_id"],
        "agent_as_of": as_of,
        "agent_created_at": run["created_at"],
        "fitted_run_id": result["fitted_run_id"],
        "n_sims": n_sims,
        "teams": {team: stage_impacts(agent_reach[team], then[team], now[team], held_reach[team]) for team in selected},
        "fixtures": [_fixture_block(f) for f in in_play],
        "series": [
            {
                "fetched_at": state.fetched_at,
                "teams": {
                    team: estimated_stages(agent_reach[team], then[team], result["legs"][leg][team])
                    for team in selected
                },
            }
            for state, leg in zip(states, point_leg, strict=True)
        ],
    }
    return Impact.model_validate(payload)


async def _live_state(deps: Deps) -> LiveState | None:
    raw = await deps.storage.read(LIVE_STATE.key())
    if raw is None:
        return None
    try:
        return LiveState.model_validate_json(raw)
    except ValidationError:
        return None
