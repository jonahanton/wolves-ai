from __future__ import annotations

import json
from typing import Any

from tests.fakes import build_test_app, client_for
from wolves_backend.routes.live import MAX_HISTORY_POINTS, _sample


def _state_body(minute: int, p_home: float, **overrides: Any) -> dict[str, Any]:
    body = {
        "schema_version": 1,
        "generated_at": "2026-06-17T20:31:00+00:00",
        "fetched_at": f"2026-06-17T20:{minute:02d}:00+00:00",
        "stale_after": "2026-06-17T20:32:00+00:00",
        "source": "api-football",
        "poll_status": "ok",
        "live_match_count": 1,
        "fixtures": [
            {
                "external_id": 1300022,
                "match": 22,
                "status": "live",
                "kickoff": "2026-06-17T20:00:00+00:00",
                "minute": minute,
                "home_id": "england",
                "away_id": "croatia",
                "home_name": "England",
                "away_name": "Croatia",
                "home_goals": 1,
                "away_goals": 0,
                "home_reds": 0,
                "away_reds": 0,
                "forecast": {"source": "in_match", "p_home": p_home, "p_draw": 0.15, "p_away": 0.07},
            }
        ],
        "title_probs": {"england": 0.1},
        "title_deltas_pp": {"england": 0.4},
    }
    body.update(overrides)
    return body


def _write_point(tmp_path, time: str, body: dict[str, Any]) -> None:
    day_dir = tmp_path / "live" / "history" / "2026-06-17"
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / f"{time}.json").write_text(json.dumps(body), encoding="utf-8")


async def test_history_thins_points_to_fixture_progression_in_key_order(tmp_path):
    _write_point(tmp_path, "200500", _state_body(5, 0.52))
    _write_point(tmp_path, "200300", _state_body(3, 0.5))

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live/history/2026-06-17")

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-06-17"
    assert [point["fixtures"][0]["minute"] for point in payload["points"]] == [3, 5]
    fixture = payload["points"][0]["fixtures"][0]
    assert set(fixture) == {"external_id", "match", "status", "minute", "home_goals", "away_goals", "forecast"}
    assert fixture["forecast"]["p_home"] == 0.5


async def test_history_skips_malformed_points_rather_than_failing_the_day(tmp_path):
    _write_point(tmp_path, "200300", _state_body(3, 0.5))
    day_dir = tmp_path / "live" / "history" / "2026-06-17"
    (day_dir / "200400.json").write_text("{not json", encoding="utf-8")

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live/history/2026-06-17")

    assert response.status_code == 200
    assert len(response.json()["points"]) == 1


async def test_history_is_404_when_the_day_has_no_points(tmp_path):
    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live/history/2026-06-17")
    assert response.status_code == 404


async def test_history_rejects_a_non_date_path(tmp_path):
    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live/history/state")
    assert response.status_code == 400


def test_sampling_bounds_a_long_day_and_keeps_both_ends():
    keys = [f"{i:06d}" for i in range(1000)]
    sampled = _sample(keys, MAX_HISTORY_POINTS)
    assert len(sampled) == MAX_HISTORY_POINTS
    assert sampled[0] == keys[0]
    assert sampled[-1] == keys[-1]
