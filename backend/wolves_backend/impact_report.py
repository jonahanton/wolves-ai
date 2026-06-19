"""Build and serve the agent-forecast impact report so a read never simulates."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from wolves.insights.impact import exit_impacts, stage_impacts
from wolves.live_state import LiveFixture, LiveState
from wolves.models.inmatch import MatchState
from wolves.models.live_signals import LiveSignals
from wolves.s3.layout import LIVE_IMPACT, LIVE_STATE
from wolves.sim.format import PlayedResult
from wolves.sim.result_set import result_set_from_entries
from wolves.snapshot import ResultSetBlock, ResultSetEntry
from wolves_backend.live_history import day_states
from wolves_backend.models import Impact
from wolves_backend.sim import Leg

if TYPE_CHECKING:
    from wolves.forecast import Forecaster
    from wolves.models.contracts import ScorelineDistribution
    from wolves_backend.deps import Deps

logger = logging.getLogger(__name__)

REACH_STAGES = ("r32", "r16", "qf", "sf", "final")
# Coarse curve keyframes; the per-minute stat track drives the bars cheaply.
REPLAY_STRIDE_MIN = 5


class NoAgentForecastError(Exception):
    """No agent snapshot has been published yet, so there is nothing to measure."""


class MalformedAgentForecastError(Exception):
    """The published agent snapshot could not be parsed."""


class ImpactService:
    """The single impact report: rebuilt each live pass, cached, mirrored to an artifact."""

    def __init__(self) -> None:
        self._cached: Impact | None = None
        self._lock = asyncio.Lock()

    async def get(self, deps: Deps) -> Impact:
        """The current report; computed once on a cold cache, never on the hot path after."""
        if self._cached is not None:
            return self._cached
        async with self._lock:
            if self._cached is None:
                self._cached = await self._load_or_build(deps)
            return self._cached

    async def refresh(self, deps: Deps) -> None:
        """Recompute and publish the report; called every live pass and on boot."""
        async with self._lock:
            report = await build_impact(deps)
            self._cached = report
            await asyncio.to_thread(self._publish, deps, report)

    async def _load_or_build(self, deps: Deps) -> Impact:
        raw = await deps.storage.read(LIVE_IMPACT.key())
        if raw is not None:
            try:
                return Impact.model_validate_json(raw)
            except ValueError:
                logger.warning("published impact artifact is malformed; recomputing")
        report = await build_impact(deps)
        await asyncio.to_thread(self._publish, deps, report)
        return report

    @staticmethod
    def _publish(deps: Deps, report: Impact) -> None:
        deps.engine.artifacts.put(LIVE_IMPACT, report.model_dump_json(by_alias=True))


async def build_impact(deps: Deps) -> Impact:
    """Measure the agent forecast's movement for every team, results and in-game."""
    refs = await deps.snapshots.index()
    agent_ref = next((ref for ref in refs if ref.kind == "agent"), None)
    body = await deps.storage.read(agent_ref.key) if agent_ref else None
    if body is None:
        raise NoAgentForecastError
    try:
        snapshot = json.loads(body)
        run = snapshot["run"]
        created_at = run["created_at"]
    except (ValueError, KeyError, TypeError) as exc:
        raise MalformedAgentForecastError from exc

    agent_stages = _agent_stages(snapshot)
    as_of = run.get("as_of") or created_at[:10]
    current_result_set = await deps.engine.result_set()
    agent_result_set = _agent_result_set(snapshot, current_result_set)
    live = await _live_state(deps)
    in_play = [f for f in live.fixtures if f.status == "live"] if live else []
    serving = _live_is_fresh(live) and deps.engine.ready
    forecaster = deps.engine.forecaster
    live_dists = _live_distributions(forecaster, in_play) if serving else {}
    knockout_ids = {m.match for m in forecaster.fmt.knockout}
    stat_history = await _stat_history(deps, live) if serving else {}

    n_sims = deps.engine.settings.impact_n_sims
    seed = 0
    legs: dict[str, Leg] = {
        "then": Leg(results=_played(agent_result_set), fitted_run_id=run["run_id"]),
        "now": Leg(results=_played(current_result_set)),
        "live": Leg(results=_played(current_result_set), live_distributions=live_dists or None),
    }
    result = await deps.engine.reach_legs(legs, n_sims=n_sims, seed=seed)
    then, now, live_reach = result["legs"]["then"], result["legs"]["now"], result["legs"]["live"]

    payload = {
        "agent_run_id": run["run_id"],
        "agent_as_of": as_of,
        "agent_created_at": created_at,
        "then_basis": result["bases"]["then"],
        "now_basis": result["bases"]["now"],
        "current_fit_run_id": result["fitted_run_id"],
        "current_fit_as_of": forecaster.state.as_of.isoformat(),
        "dataset_id": forecaster.state.dataset_id,
        "agent_result_set_digest": agent_result_set.digest,
        "current_result_set_digest": current_result_set.digest,
        "live_mode": "in_match_distribution" if live_dists else "none",
        "n_sims": n_sims,
        "seed": seed,
        "parameter_uncertainty": False,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "results_since_agent": _results_since_agent(agent_result_set, current_result_set),
        "fixtures": [
            _fixture_block(
                f,
                _live_wdl_frames(
                    forecaster, f, knockout=f.match in knockout_ids, history=stat_history.get(f.match, [])
                )
                if serving
                else None,
                _stat_track(f, stat_history.get(f.match, [])) if serving else [],
            )
            for f in in_play
        ],
        "teams": {
            team: _team_impact(agent_stages[team], then[team], now[team], live_reach[team]) for team in agent_stages
        },
    }
    return Impact.model_validate(payload)


def _match_state(fixture: LiveFixture) -> MatchState | None:
    if fixture.minute is None or fixture.home_goals is None or fixture.away_goals is None:
        return None
    return MatchState(
        minute=float(fixture.minute),
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        home_reds=fixture.home_reds,
        away_reds=fixture.away_reds,
        period=fixture.period,
    )


def _live_distributions(forecaster: Forecaster, fixtures: list[LiveFixture]) -> dict[int, ScorelineDistribution]:
    out: dict[int, ScorelineDistribution] = {}
    for f in fixtures:
        if f.status != "live" or f.match is None or f.home_id is None or f.away_id is None:
            continue
        state = _match_state(f)
        if state is not None:
            out[f.match] = forecaster.live_distribution(f.home_id, f.away_id, state)
    return out


def _replay_states(fixture: LiveFixture) -> list[MatchState]:
    """Replay keyframes: a minute grid for held-score drift plus the post-goal jumps."""
    now = _match_state(fixture)
    if now is None:
        return []
    goals = sorted((g for g in fixture.goals if g.minute <= now.minute), key=lambda g: g.minute)

    def score_at(minute: float) -> tuple[int, int]:
        home = sum(1 for g in goals if g.side == "home" and g.minute <= minute)
        away = sum(1 for g in goals if g.side == "away" and g.minute <= minute)
        return home, away

    def state_at(minute: float, *, post_goal: bool) -> MatchState:
        home, away = score_at(minute if post_goal else minute - 1e-6)
        return MatchState(
            minute=minute,
            home_goals=home,
            away_goals=away,
            home_reds=now.home_reds,
            away_reds=now.away_reds,
            period=now.period,
        )

    minutes: dict[float, bool] = {0.0: False}
    grid = REPLAY_STRIDE_MIN
    while grid < now.minute:
        minutes.setdefault(float(grid), False)
        grid += REPLAY_STRIDE_MIN
    for goal in goals:
        minutes[float(goal.minute)] = True
    minutes[now.minute] = minutes.get(now.minute, False)

    return [state_at(minute, post_goal=post_goal) for minute, post_goal in sorted(minutes.items())]


def _wdl(draws: tuple[list[float], list[float], list[float]]) -> dict[str, list[float]]:
    return {"p_home": draws[0], "p_draw": draws[1], "p_away": draws[2]}


def _signals(fixture: LiveFixture) -> LiveSignals | None:
    """Live shots and possession from the schedule-oriented fixture; None when
    the provider has published neither yet."""
    signals = LiveSignals(
        home_shots_on=fixture.home_shots_on,
        away_shots_on=fixture.away_shots_on,
        home_possession=fixture.home_possession,
        away_possession=fixture.away_possession,
    )
    return signals if signals.has_shots or signals.has_possession else None


async def _stat_history(deps: Deps, live: LiveState | None) -> dict[int, list[LiveFixture]]:
    """Per live match, the polled fixture snapshots that published a signal,
    ascending by minute. The replay reads the latest snapshot at or before each
    keyframe, so both the curve and the stat bars track how the pace built up."""
    if live is None:
        return {}
    # Poll date can differ from kickoff date for a match spanning midnight; cover both.
    dates = {fixture.kickoff[:10] for fixture in live.fixtures if fixture.status == "live"}
    dates.add(live.generated_at[:10])
    states = [state for day in sorted(dates) for state in await day_states(deps.storage, day)]
    history: dict[int, list[LiveFixture]] = {}
    for state in sorted(states, key=lambda s: s.fetched_at):
        for fixture in state.fixtures:
            if fixture.match is None or fixture.minute is None:
                continue
            if _signals(fixture) is not None:
                history.setdefault(fixture.match, []).append(fixture)
    return {match: sorted(snaps, key=lambda snap: snap.minute or 0) for match, snaps in history.items()}


def _snapshot_at(history: list[LiveFixture], minute: float) -> LiveFixture | None:
    """The latest snapshot at or before this keyframe minute, or None when no poll
    had landed yet (keeping the pre-match anchor and no stat bars for that frame)."""
    found: LiveFixture | None = None
    for snap in history:
        if (snap.minute or 0) > minute:
            break
        found = snap
    return found


def _stat_point(minute: int, snap: LiveFixture | None) -> dict[str, int | float | None]:
    return {
        "minute": minute,
        "home_shots_on": snap.home_shots_on if snap else None,
        "away_shots_on": snap.away_shots_on if snap else None,
        "home_total_shots": snap.home_total_shots if snap else None,
        "away_total_shots": snap.away_total_shots if snap else None,
        "home_possession": snap.home_possession if snap else None,
        "away_possession": snap.away_possession if snap else None,
    }


def _stat_track(fixture: LiveFixture, history: list[LiveFixture]) -> list[dict[str, int | float | None]]:
    """One light stat point per match minute, driving the bars without the curve's bulk."""
    if fixture.minute is None:
        return []
    track = [_stat_point(minute, _snapshot_at(history, minute)) for minute in range(fixture.minute + 1)]
    if track and track[-1]["home_shots_on"] is None and _signals(fixture) is not None:
        track[-1] = _stat_point(fixture.minute, fixture)
    return track


def _live_wdl_frames(
    forecaster: Forecaster, fixture: LiveFixture, *, knockout: bool, history: list[LiveFixture]
) -> tuple[dict[str, list[float]], list[dict[str, Any]]] | None:
    """Current per-draw W/D/L plus a keyframe per goal, all from one shared rate
    sample. Each keyframe blends the signals as they stood at that minute."""
    if fixture.home_id is None or fixture.away_id is None:
        return None
    states = _replay_states(fixture)
    if not states:
        return None
    snaps = [_snapshot_at(history, state.minute) for state in states]
    if snaps[-1] is None:
        # The latest keyframe always reflects the freshest published snapshot.
        snaps[-1] = fixture
    signals_at = [_signals(snap) if snap else None for snap in snaps]
    frames = forecaster.live_wdl_draws_at(
        fixture.home_id, fixture.away_id, states, knockout=knockout, signals_at=signals_at
    )
    keyframes = [
        {
            "minute": int(state.minute),
            "home_goals": state.home_goals,
            "away_goals": state.away_goals,
            "wdl": _wdl(frame),
        }
        for state, frame in zip(states, frames, strict=True)
    ]
    return _wdl(frames[-1]), keyframes


def _fixture_block(
    fixture: LiveFixture,
    frames: tuple[dict[str, list[float]], list[dict[str, Any]]] | None,
    stat_track: list[dict[str, int | float | None]],
) -> dict[str, Any]:
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
        "home_shots_on": fixture.home_shots_on,
        "away_shots_on": fixture.away_shots_on,
        "home_total_shots": fixture.home_total_shots,
        "away_total_shots": fixture.away_total_shots,
        "home_possession": fixture.home_possession,
        "away_possession": fixture.away_possession,
        "wdl_draws": frames[0] if frames else None,
        "wdl_keyframes": frames[1] if frames else [],
        "stat_track": stat_track,
    }


async def _live_state(deps: Deps) -> LiveState | None:
    raw = await deps.storage.read(LIVE_STATE.key())
    if raw is None:
        return None
    try:
        return LiveState.model_validate_json(raw)
    except ValueError:
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
            match=entry.match, home_goals=entry.home_goals, away_goals=entry.away_goals, winner=entry.winner
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
    return {**entry.model_dump(mode="json"), "kind": kind}


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
    agent: dict[str, float], then: dict[str, float], now: dict[str, float], live: dict[str, float]
) -> dict[str, Any]:
    stages = stage_impacts(agent, then, now, live)
    return {
        "title": stages["champion"],
        "reach": {stage: stages[stage] for stage in REACH_STAGES},
        "exit": exit_impacts(agent, then, now, live),
    }
