from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from tests.fakes import build_test_app, client_for, published_engine
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import PlayedResult
from wolves.sim.results_store import ResultsStore

STAGES = {"r32": 0.95, "r16": 0.6, "qf": 0.4, "sf": 0.25, "final": 0.15, "champion": 0.08}


def write_agent_snapshot(runs_root, fmt) -> None:
    teams = [
        {
            "team_id": t.id,
            "name": t.id,
            "group": "A",
            "elo": 1800,
            "champion_prob": STAGES["champion"],
            "reach_probs": {k: v for k, v in STAGES.items() if k != "champion"},
        }
        for t in fmt.teams
    ]
    snapshot = {
        "run": {
            "run_id": "agent-20260611-133152",
            "created_at": "2026-06-11T14:15:00+00:00",
            "as_of": "2026-06-11",
            "n_sims": 50000,
            "engine_version": "0.2.0",
            "kind": "agent",
        },
        "focus": {"team_id": fmt.teams[2].id},
        "teams": teams,
        "matches": [{"match": m.match} for m in fmt.group_matches],
    }
    path = runs_root / "snapshots" / "2026" / "06" / "11" / "agent-20260611-133152.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")


def live_state(
    fmt,
    *,
    home_goals: int,
    minute: int = 61,
    fetched_at: str = "2026-06-12T15:00:00+00:00",
    goals: list | None = None,
    stats: dict | None = None,
) -> dict:
    opener = fmt.group_matches[0]
    stale_after = (datetime.now(UTC) + timedelta(minutes=2)).isoformat(timespec="seconds")
    return {
        "schema_version": 1,
        "generated_at": fetched_at,
        "fetched_at": fetched_at,
        "stale_after": stale_after,
        "live_match_count": 1,
        "fixtures": [
            {
                "external_id": 1,
                "match": opener.match,
                "status": "live",
                "kickoff": "2026-06-12T14:00:00+00:00",
                "minute": minute,
                "home_id": opener.home,
                "away_id": opener.away,
                "home_name": opener.home,
                "away_name": opener.away,
                "home_goals": home_goals,
                "away_goals": 0,
                "goals": goals or [],
                "forecast": {"source": "in_match", "p_home": 0.9, "p_away": 0.02, "p_draw": 0.08},
                **(stats or {}),
            }
        ],
    }


async def _ingame_shift(tmp_path, *, home_goals: int, minute: int) -> float:
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    (tmp_path / "live").mkdir(exist_ok=True)
    (tmp_path / "live" / "state.json").write_text(
        json.dumps(live_state(fmt, home_goals=home_goals, minute=minute)), encoding="utf-8"
    )
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        body = (await client.get("/impact")).json()
    home = fmt.group_matches[0].home
    return body["teams"][home]["reach"]["r16"]["fromIngamePp"]


async def test_impact_estimates_in_game_movement_on_the_agent_scale(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "state.json").write_text(json.dumps(live_state(fmt, home_goals=9)), encoding="utf-8")

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 200
    body = response.json()
    assert body["agentRunId"] == "agent-20260611-133152"
    assert body["liveMode"] == "in_match_distribution"
    home = fmt.group_matches[0].home
    assert home in body["teams"]
    r32 = body["teams"][home]["reach"]["r32"]
    assert r32["agent"] == 0.95
    assert r32["afterResults"] == r32["agent"]
    assert r32["fromResultsPp"] == 0.0
    assert r32["fromIngamePp"] > 0.0
    assert r32["estimated"] > r32["agent"]
    assert body["teams"][home]["title"]["agent"] == 0.08
    assert set(body["teams"][home]["exit"]) == {"groups", "r32", "r16", "qf", "sf", "final", "champion"}

    fixture = body["fixtures"][0]
    assert (fixture["homeGoals"], fixture["minute"]) == (9, 61)
    assert "series" not in body
    wdl = fixture["wdlDraws"]
    assert len(wdl["pHome"]) == len(wdl["pDraw"]) == len(wdl["pAway"]) > 1
    assert all(0.0 <= p <= 1.0 for p in wdl["pHome"])


async def test_live_wdl_keyframes_step_through_each_goal(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    (tmp_path / "live").mkdir()
    state = live_state(
        fmt,
        home_goals=2,
        minute=70,
        goals=[{"minute": 18, "side": "home"}, {"minute": 55, "side": "home"}],
    )
    (tmp_path / "live" / "state.json").write_text(json.dumps(state), encoding="utf-8")

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        body = (await client.get("/impact")).json()

    keyframes = body["fixtures"][0]["wdlKeyframes"]
    frames = [(k["minute"], k["homeGoals"], k["awayGoals"]) for k in keyframes]
    # Minutes are strictly increasing and span kickoff to now.
    assert [k["minute"] for k in keyframes] == sorted(k["minute"] for k in keyframes)
    assert frames[0] == (0, 0, 0)
    assert frames[-1] == (70, 2, 0)
    # The exact post-goal states are present, so the curve jumps when the score does.
    assert (18, 1, 0) in frames
    assert (55, 2, 0) in frames
    # Intermediate minute-cadence frames exist at a held score, giving the drift.
    assert any(0 < m < 18 and (h, a) == (0, 0) for m, h, a in frames)
    # Every keyframe shares the same draw count, so the curves are frame-comparable.
    counts = {len(k["wdl"]["pHome"]) for k in keyframes}
    assert len(counts) == 1 and counts.pop() > 1
    # The final keyframe is the current spread the row shows at rest.
    assert keyframes[-1]["wdl"] == body["fixtures"][0]["wdlDraws"]


async def test_live_shot_dominance_reaches_the_served_wdl_spread(tmp_path):
    """The blend must survive the backend path: a level live game where the home
    side is out-shooting the away side serves a higher home win mass and exposes
    the raw shot stats on the fixture."""

    async def served_spread(stats: dict | None) -> tuple[float, dict]:
        engine = published_engine(tmp_path / ("with" if stats else "without"))
        await engine.boot()
        fmt = engine.forecaster.fmt
        run_dir = tmp_path / ("with" if stats else "without")
        write_agent_snapshot(run_dir, fmt)
        (run_dir / "live").mkdir(exist_ok=True)
        (run_dir / "live" / "state.json").write_text(
            json.dumps(live_state(fmt, home_goals=0, minute=70, stats=stats)), encoding="utf-8"
        )
        app = build_test_app(storage_dir=run_dir, engine=engine)
        async with client_for(app) as client:
            fixture = (await client.get("/impact")).json()["fixtures"][0]
        return sum(fixture["wdlDraws"]["pHome"]) / len(fixture["wdlDraws"]["pHome"]), fixture

    base, _ = await served_spread(None)
    blended, fixture = await served_spread(
        {"home_shots_on": 9, "away_shots_on": 1, "home_possession": 0.62, "away_possession": 0.38}
    )
    assert blended > base + 0.02
    assert (fixture["homeShotsOn"], fixture["awayShotsOn"]) == (9, 1)
    assert fixture["homePossession"] == 0.62


async def test_replay_keyframes_evolve_with_the_recorded_shot_history(tmp_path):
    """A poll-history burst of home shots at an early minute lifts that keyframe's
    home win mass above the same frame built without any history."""

    async def home_at_minute(history: list[dict] | None, keyframe_minute: int) -> float:
        run_dir = tmp_path / ("with" if history else "without")
        engine = published_engine(run_dir)
        await engine.boot()
        fmt = engine.forecaster.fmt
        write_agent_snapshot(run_dir, fmt)
        (run_dir / "live").mkdir(exist_ok=True)
        state = live_state(fmt, home_goals=0, minute=80)
        (run_dir / "live" / "state.json").write_text(json.dumps(state), encoding="utf-8")
        for point in history or []:
            store = ArtifactStore(engine.settings)
            stamp = point["time"]
            body = json.dumps(
                live_state(
                    fmt,
                    home_goals=0,
                    minute=point["minute"],
                    fetched_at=f"2026-06-12T{stamp}+00:00",
                    stats={"home_shots_on": point["home_shots_on"], "away_shots_on": point["away_shots_on"]},
                )
            )
            store.put_text(f"live/history/2026-06-12/{stamp.replace(':', '')}.json", body)
        app = build_test_app(storage_dir=run_dir, engine=engine)
        async with client_for(app) as client:
            keyframes = (await client.get("/impact")).json()["fixtures"][0]["wdlKeyframes"]
        frame = min(keyframes, key=lambda k: abs(k["minute"] - keyframe_minute))
        return sum(frame["wdl"]["pHome"]) / len(frame["wdl"]["pHome"])

    history = [
        {"time": "14:26:30", "minute": 27, "home_shots_on": 5, "away_shots_on": 0},
        # A second poll at the same minute must not break the sort of the series.
        {"time": "14:27:00", "minute": 27, "home_shots_on": 6, "away_shots_on": 0},
        {"time": "15:00:00", "minute": 80, "home_shots_on": 7, "away_shots_on": 5},
    ]
    base = await home_at_minute(None, 27)
    evolved = await home_at_minute(history, 27)
    assert evolved > base + 0.02


async def test_replay_tolerates_pre_deploy_history_without_stat_fields(tmp_path):
    """History points written before this feature carry no stat fields. They must
    parse, contribute no signal, and leave the early keyframes on the pre-match
    anchor rather than 500 the report."""
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "state.json").write_text(
        json.dumps(live_state(fmt, home_goals=0, minute=70)), encoding="utf-8"
    )
    opener = fmt.group_matches[0]
    legacy = {
        "schema_version": 1,
        "generated_at": "2026-06-12T14:30:00+00:00",
        "fetched_at": "2026-06-12T14:30:00+00:00",
        "stale_after": "2026-06-12T14:32:00+00:00",
        "fixtures": [
            {
                "external_id": 1,
                "match": opener.match,
                "status": "live",
                "kickoff": "2026-06-12T14:00:00+00:00",
                "minute": 30,
                "home_id": opener.home,
                "away_id": opener.away,
                "home_name": opener.home,
                "away_name": opener.away,
                "home_goals": 0,
                "away_goals": 0,
            }
        ],
    }
    ArtifactStore(engine.settings).put_text("live/history/2026-06-12/143000.json", json.dumps(legacy))

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")
    assert response.status_code == 200
    keyframes = response.json()["fixtures"][0]["wdlKeyframes"]
    assert len(keyframes) > 1


async def test_impact_requires_a_published_agent_forecast(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 404


async def test_impact_rejects_a_malformed_agent_snapshot(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    path = tmp_path / "snapshots" / "2026" / "06" / "11" / "agent-20260611-133152.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"teams": [], "focus": {}}), encoding="utf-8")
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")
    assert response.status_code == 502
    assert response.json() == {"error": "published agent forecast is malformed"}


async def test_then_leg_simulates_under_the_agent_runs_own_fitted_state(tmp_path):
    from dataclasses import replace

    import numpy as np

    from wolves.s3.artifacts import ArtifactStore
    from wolves.s3.fitted import FittedStateStore

    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    strengths = engine.forecaster.state.strengths - 0.3
    strengths[np.argmax(strengths)] += 0.6
    shifted = replace(engine.forecaster.state, strengths=strengths)
    store = FittedStateStore(ArtifactStore(engine.settings))
    store.publish(shifted, run_id="agent-20260611-133152")
    # Publishing repoints latest; the current fit must stay the original state.
    store.publish(engine.forecaster.state, run_id="run-test")
    await engine.refresh()

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 200
    body = response.json()
    assert body["thenBasis"] == "run:agent-20260611-133152"
    moved = [team for team, impact in body["teams"].items() if impact["title"]["fromResultsPp"] != 0.0]
    assert moved, "a refit between the agent run and now must show in the results component"


async def test_then_leg_falls_back_to_the_current_fit_without_an_artifact(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    write_agent_snapshot(tmp_path, engine.forecaster.fmt)
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 200
    assert response.json()["thenBasis"] == "current"


async def test_impact_infers_old_snapshot_result_set_from_open_matches(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    opener = fmt.group_matches[0]
    ResultsStore(ArtifactStore(engine.settings)).record(
        {opener.match: PlayedResult(match=opener.match, home_goals=2, away_goals=0)}
    )
    await engine.refresh()
    write_agent_snapshot(tmp_path, fmt)

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 200
    body = response.json()
    [result] = body["resultsSinceAgent"]
    assert result | {"fetchedAt": None} == {
        "match": opener.match,
        "homeId": opener.home,
        "awayId": opener.away,
        "homeGoals": 2,
        "awayGoals": 0,
        "winner": None,
        "sourceFixtureId": None,
        "fetchedAt": None,
        "kind": "new",
    }
    assert result["fetchedAt"] is not None
    assert body["agentResultSetDigest"] != body["currentResultSetDigest"]


async def test_later_identical_lead_moves_reach_more_than_an_early_one(tmp_path):
    early = await _ingame_shift(tmp_path / "early", home_goals=1, minute=20)
    late = await _ingame_shift(tmp_path / "late", home_goals=1, minute=85)
    assert late > early > 0.0


async def test_no_live_game_gives_zero_ingame_delta(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        body = (await client.get("/impact")).json()
    assert body["liveMode"] == "none"
    for team in body["teams"].values():
        assert team["reach"]["r32"]["fromIngamePp"] == 0.0


async def test_impact_suppresses_ingame_deltas_when_live_state_is_stale(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    stale = live_state(fmt, home_goals=9)
    stale["stale_after"] = "2026-06-12T15:02:00+00:00"
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "state.json").write_text(json.dumps(stale), encoding="utf-8")

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 200
    body = response.json()
    home = fmt.group_matches[0].home
    assert body["liveMode"] == "none"
    assert body["teams"][home]["reach"]["r32"]["fromIngamePp"] == 0.0
