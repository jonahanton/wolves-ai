from __future__ import annotations

import json
from typing import Any

from tests.fakes import build_test_app, client_for


def _state_body(**overrides: Any) -> dict[str, Any]:
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
    body.update(overrides)
    return body


def _write_state(tmp_path, body: dict[str, Any]) -> None:
    (tmp_path / "live").mkdir(exist_ok=True)
    (tmp_path / "live" / "state.json").write_text(json.dumps(body), encoding="utf-8")


async def test_live_state_serves_the_current_artifact(tmp_path):
    _write_state(tmp_path, _state_body())

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json()["fixtures"][0]["forecast"]["source"] == "in_match"


async def test_live_state_serves_a_failed_poll_with_carried_over_fixtures(tmp_path):
    _write_state(tmp_path, _state_body(poll_status="failed", message="api-football timed out"))

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["poll_status"] == "failed"
    assert payload["message"] == "api-football timed out"
    assert payload["fixtures"][0]["home_name"] == "Mexico"


async def test_live_state_honours_if_none_match_until_the_state_changes(tmp_path):
    _write_state(tmp_path, _state_body())

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        first = await client.get("/live")
        etag = first.headers["etag"]
        assert first.status_code == 200
        assert first.headers["cache-control"] == "no-cache"

        cached = await client.get("/live", headers={"If-None-Match": etag})
        assert cached.status_code == 304
        assert cached.headers["etag"] == etag
        assert cached.content == b""

        _write_state(tmp_path, _state_body(live_match_count=2))
        fresh = await client.get("/live", headers={"If-None-Match": etag})
        assert fresh.status_code == 200
        assert fresh.headers["etag"] != etag


async def test_live_state_404s_when_no_poll_has_landed(tmp_path):
    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 404


async def test_live_state_rejects_malformed_artifacts(tmp_path):
    _write_state(tmp_path, {"fixtures": []})

    async with client_for(build_test_app(storage_dir=tmp_path)) as client:
        response = await client.get("/live")

    assert response.status_code == 502
    assert response.json() == {"error": "live state is malformed"}
