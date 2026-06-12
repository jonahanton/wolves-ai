from __future__ import annotations

import json
from typing import Any

from tests.fakes import build_test_app, client_for, published_engine


def _state_body(home_goals: int = 9) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-12T19:31:00+00:00",
        "fetched_at": "2026-06-12T19:30:00+00:00",
        "stale_after": "2026-06-12T19:32:00+00:00",
        "source": "api-football",
        "poll_status": "ok",
        "live_match_count": 1,
        "fixtures": [
            {
                "external_id": 1300001,
                "match": 1,
                "status": "live",
                "kickoff": "2026-06-12T19:00:00+00:00",
                "minute": 63,
                "home_id": "mexico",
                "away_id": "south_africa",
                "home_name": "Mexico",
                "away_name": "South Africa",
                "home_goals": home_goals,
                "away_goals": 0,
                "forecast": {"source": "in_match", "p_home": 0.99, "p_draw": 0.005, "p_away": 0.005},
            }
        ],
        "title_probs": {"mexico": 0.2},
        "title_deltas_pp": {"mexico": 1.4},
    }


def _write_state(tmp_path, body: dict[str, Any]) -> None:
    (tmp_path / "live").mkdir(exist_ok=True)
    (tmp_path / "live" / "state.json").write_text(json.dumps(body), encoding="utf-8")


async def test_live_state_carries_held_score_deltas_when_the_engine_is_ready(tmp_path):
    _write_state(tmp_path, _state_body())
    engine = published_engine(tmp_path)
    await engine.boot()

    async with client_for(build_test_app(storage_dir=tmp_path, engine=engine)) as client:
        response = await client.get("/live")

    assert response.status_code == 200
    hold = response.json()["scores_hold"]
    home = engine.forecaster.fmt.group_matches[0].home
    assert hold["fitted_run_id"] == "run-test"
    assert hold["deltas_pp"][home] > 0
    assert 0.99 < sum(hold["held"].values()) < 1.01


async def test_live_state_stays_raw_before_the_engine_boots(tmp_path):
    _write_state(tmp_path, _state_body())

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 200
    assert "scores_hold" not in response.json()
