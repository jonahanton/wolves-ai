from __future__ import annotations

import json

from tests.fakes import build_test_app, client_for


async def test_live_state_serves_the_current_artifact(tmp_path):
    body = {
        "schema_version": 1,
        "generated_at": "2026-06-11T19:31:00+00:00",
        "fetched_at": "2026-06-11T19:30:00+00:00",
        "stale_after": "2026-06-11T19:32:00+00:00",
        "source": "api-football",
        "poll_status": "ok",
        "live_match_count": 1,
        "fixtures": [
            {
                "external_id": 1300001,
                "match": 1,
                "status": "live",
                "kickoff": "2026-06-11T19:00:00+00:00",
                "minute": 63,
                "home_id": "mexico",
                "away_id": "south_africa",
                "home_name": "Mexico",
                "away_name": "South Africa",
                "home_goals": 1,
                "away_goals": 0,
                "home_reds": 0,
                "away_reds": 0,
                "forecast": {"source": "in_match", "p_home": 0.78, "p_draw": 0.15, "p_away": 0.07},
            }
        ],
        "title_probs": {"mexico": 0.2},
        "title_deltas_pp": {"mexico": 1.4},
    }
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "state.json").write_text(json.dumps(body), encoding="utf-8")

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json()["fixtures"][0]["forecast"]["source"] == "in_match"


async def test_live_state_404s_when_no_poll_has_landed(tmp_path):
    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 404


async def test_live_state_rejects_malformed_artifacts(tmp_path):
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "state.json").write_text('{"fixtures": []}', encoding="utf-8")

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 502
    assert response.json() == {"error": "live state is malformed"}
