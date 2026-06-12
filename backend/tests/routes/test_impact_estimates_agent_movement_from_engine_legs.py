from __future__ import annotations

import json
from datetime import UTC, datetime

from tests.fakes import build_test_app, client_for, published_engine

STAGES = {"r32": 0.95, "r16": 0.6, "qf": 0.4, "sf": 0.25, "final": 0.15, "champion": 0.08}


def write_agent_snapshot(runs_root, fmt) -> None:
    teams = [{"team_id": t.id, "name": t.id, "group": "A", "elo": 1800, "reach_probs": STAGES} for t in fmt.teams]
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
    }
    path = runs_root / "snapshots" / "2026" / "06" / "11" / "agent-20260611-133152.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot), encoding="utf-8")


def live_state(fmt, *, home_goals: int) -> dict:
    opener = fmt.group_matches[0]
    return {
        "schema_version": 1,
        "generated_at": "2026-06-12T15:00:00+00:00",
        "fetched_at": "2026-06-12T15:00:00+00:00",
        "stale_after": "2026-06-12T15:02:00+00:00",
        "live_match_count": 1,
        "fixtures": [
            {
                "external_id": 1,
                "match": opener.match,
                "status": "live",
                "kickoff": "2026-06-12T14:00:00+00:00",
                "minute": 61,
                "home_id": opener.home,
                "away_id": opener.away,
                "home_name": opener.home,
                "away_name": opener.away,
                "home_goals": home_goals,
                "away_goals": 0,
                "forecast": {"source": "in_match", "p_home": 0.9, "p_away": 0.02, "p_draw": 0.08},
            }
        ],
    }


async def test_impact_estimates_in_game_movement_on_the_agent_scale(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    fmt = engine.forecaster.fmt
    write_agent_snapshot(tmp_path, fmt)
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "state.json").write_text(json.dumps(live_state(fmt, home_goals=9)), encoding="utf-8")
    today = datetime.now(UTC).date().isoformat()
    history = tmp_path / "live" / "history" / today
    history.mkdir(parents=True)
    (history / "140500.json").write_text(json.dumps(live_state(fmt, home_goals=0)), encoding="utf-8")
    (history / "150000.json").write_text(json.dumps(live_state(fmt, home_goals=9)), encoding="utf-8")

    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 200
    body = response.json()
    assert body["agentRunId"] == "agent-20260611-133152"
    home = fmt.group_matches[0].home
    assert home in body["teams"]
    r32 = body["teams"][home]["r32"]
    assert r32["agent"] == 0.95
    assert r32["fromResultsPp"] == 0.0
    assert r32["fromIngamePp"] > 0.0
    assert r32["estimated"] > r32["agent"]

    fixture = body["fixtures"][0]
    assert (fixture["homeGoals"], fixture["minute"]) == (9, 61)
    points = body["series"]
    assert len(points) == 2
    assert points[1]["teams"][home]["r32"] > points[0]["teams"][home]["r32"]


async def test_impact_requires_a_published_agent_forecast(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/impact")

    assert response.status_code == 404
