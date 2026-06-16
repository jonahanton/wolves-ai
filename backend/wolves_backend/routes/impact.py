"""Estimated movement of the agent's published forecast, measured by the engine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from wolves.insights.impact import exit_impacts, stage_impacts
from wolves.live_state import LiveFixture, LiveState
from wolves.models.inmatch import MatchState
from wolves.s3.layout import LIVE_STATE
from wolves.sim.format import PlayedResult
from wolves.sim.result_set import result_set_from_entries
from wolves.snapshot import ResultSetBlock, ResultSetEntry
from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import Impact
from wolves_backend.sim import Leg

if TYPE_CHECKING:
    from wolves.forecast import Forecaster
    from wolves.models.contracts import ScorelineDistribution

router = APIRouter()

DepsDep = Annotated[Deps, Depends(get_deps)]

MAX_TEAMS = 12
REACH_STAGES = ("r32", "r16", "qf", "sf", "final")


def _match_state(fixture: LiveFixture) -> MatchState | None:
    # The persisted live state carries no period; regulation handles stoppage minutes cleanly.
    if fixture.minute is None or fixture.home_goals is None or fixture.away_goals is None:
        return None
    return MatchState(
        minute=float(fixture.minute),
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        home_reds=fixture.home_reds,
        away_reds=fixture.away_reds,
    )


def _live_distributions(
    forecaster: Forecaster, fixtures: list[LiveFixture]
) -> dict[int, ScorelineDistribution]:
    out: dict[int, ScorelineDistribution] = {}
    for f in fixtures:
        if f.status != "live" or f.match is None or f.home_id is None or f.away_id is None:
            continue
        state = _match_state(f)
        if state is not None:
            out[f.match] = forecaster.live_distribution(f.home_id, f.away_id, state)
    return out


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
    requested: str | None, agent_stages: dict[str, dict[str, float]], in_play: list[LiveFixture], focus: str
) -> list[str]:
    teams = [team for f in in_play for team in (f.home_id, f.away_id) if team is not None]
    if focus not in teams:
        teams.append(focus)
    if requested:
        names = [team.strip() for team in requested.split(",") if team.strip()]
        unknown = sorted(set(names) - set(agent_stages))
        if unknown:
            raise HTTPException(status_code=404, detail=f"no agent forecast for team(s) {', '.join(unknown)}")
        teams.extend(team for team in names if team not in teams)
    else:
        by_champion = sorted(agent_stages, key=lambda team: -agent_stages[team].get("champion", 0.0))
        teams.extend(team for team in by_champion[:4] if team not in teams)
    return [team for team in teams if team in agent_stages][:MAX_TEAMS]


@router.get("/impact")
async def impact(deps: DepsDep, teams: Annotated[str | None, Query()] = None) -> Impact:
    refs = await deps.snapshots.index()
    agent_ref = next((ref for ref in refs if ref.kind == "agent"), None)
    body = await deps.storage.read(agent_ref.key) if agent_ref else None
    if body is None:
        raise HTTPException(status_code=404, detail="no agent forecast published")
    snapshot = json.loads(body)
    agent_stages = _agent_stages(snapshot)
    run = snapshot["run"]
    as_of = run.get("as_of") or run["created_at"][:10]
    current_result_set = await deps.engine.result_set()
    agent_result_set = _agent_result_set(snapshot, current_result_set)
    live = await _live_state(deps)
    in_play = [f for f in live.fixtures if f.status == "live"] if live else []
    live_fresh = _live_is_fresh(live)
    live_dists = _live_distributions(deps.engine.forecaster, in_play) if live_fresh else {}
    selected = _selected_teams(teams, agent_stages, in_play, snapshot["focus"]["team_id"])
    agent_results = _played(agent_result_set)
    current_results = _played(current_result_set)
    legs: dict[str, Leg] = {
        "then": Leg(results=agent_results, fitted_run_id=run["run_id"]),
        "now": Leg(results=current_results),
        "live": Leg(results=current_results, live_distributions=live_dists or None),
    }

    n_sims = deps.engine.settings.n_sims
    seed = 0
    result = await deps.engine.reach_legs(legs, n_sims=n_sims, seed=seed)
    then, now, live_reach = result["legs"]["then"], result["legs"]["now"], result["legs"]["live"]

    payload = {
        "agent_run_id": run["run_id"],
        "agent_as_of": as_of,
        "agent_created_at": run["created_at"],
        "then_basis": result["bases"]["then"],
        "now_basis": result["bases"]["now"],
        "current_fit_run_id": result["fitted_run_id"],
        "current_fit_as_of": deps.engine.forecaster.state.as_of.isoformat(),
        "dataset_id": deps.engine.forecaster.state.dataset_id,
        "agent_result_set_digest": agent_result_set.digest,
        "current_result_set_digest": current_result_set.digest,
        "live_mode": "in_match_distribution" if live_dists else "none",
        "n_sims": n_sims,
        "seed": seed,
        "parameter_uncertainty": False,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "results_since_agent": _results_since_agent(agent_result_set, current_result_set),
        "fixtures": [_fixture_block(f) for f in in_play],
        "teams": {
            team: _team_impact(agent_stages[team], then[team], now[team], live_reach[team]) for team in selected
        },
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


def _agent_stages(snapshot: dict[str, Any]) -> dict[str, dict[str, float]]:
    stages = {}
    for team in snapshot.get("teams", []):
        reach = dict(team.get("reach_probs") or {})
        if "champion_prob" in team:
            reach["champion"] = team["champion_prob"]
        if all(stage in reach for stage in (*REACH_STAGES, "champion")):
            stages[team["team_id"]] = reach
    return stages


def _agent_result_set(snapshot: dict[str, Any], current: ResultSetBlock) -> ResultSetBlock:
    raw = snapshot.get("result_set")
    if isinstance(raw, dict) and raw.get("digest"):
        return ResultSetBlock.model_validate(raw)
    if "matches" not in snapshot:
        return ResultSetBlock()
    open_matches = {match["match"] for match in snapshot.get("matches", []) if "match" in match}
    return result_set_from_entries(entry for entry in current.results if entry.match not in open_matches)


def _played(result_set: ResultSetBlock) -> dict[int, PlayedResult]:
    return {
        entry.match: PlayedResult(
            match=entry.match,
            home_goals=entry.home_goals,
            away_goals=entry.away_goals,
            winner=entry.winner,
        )
        for entry in result_set.results
    }


def _results_since_agent(agent: ResultSetBlock, current: ResultSetBlock) -> list[dict[str, Any]]:
    previous = {entry.match: entry for entry in agent.results}
    out = []
    for entry in current.results:
        old = previous.get(entry.match)
        if old is None:
            out.append(_result_block(entry, "new"))
        elif _result_key(old) != _result_key(entry):
            out.append(_result_block(entry, "corrected"))
    return out


def _result_block(entry: ResultSetEntry, kind: str) -> dict[str, Any]:
    return {
        **entry.model_dump(mode="json"),
        "kind": kind,
    }


def _result_key(entry: ResultSetEntry) -> tuple[int, int, int, str | None]:
    return (entry.match, entry.home_goals, entry.away_goals, entry.winner)


def _live_is_fresh(live: LiveState | None) -> bool:
    if live is None or live.poll_status != "ok":
        return False
    try:
        stale_after = datetime.fromisoformat(live.stale_after)
    except ValueError:
        return False
    if stale_after.tzinfo is None:
        stale_after = stale_after.replace(tzinfo=UTC)
    return datetime.now(UTC) <= stale_after


def _team_impact(
    agent: dict[str, float],
    then: dict[str, float],
    now: dict[str, float],
    live: dict[str, float],
) -> dict[str, Any]:
    stages = stage_impacts(agent, then, now, live)
    return {
        "title": stages["champion"],
        "reach": {stage: stages[stage] for stage in REACH_STAGES},
        "exit": exit_impacts(agent, then, now, live),
    }
