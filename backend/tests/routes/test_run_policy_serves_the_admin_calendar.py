from __future__ import annotations

from tests.fakes import ADMIN_HEADERS, build_test_app, client_for, published_engine


async def test_run_policy_returns_today_and_the_full_calendar(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        anonymous = await client.get("/admin/run-policy")
        response = await client.get("/admin/run-policy", headers=ADMIN_HEADERS)

    assert anonymous.status_code == 403
    assert response.status_code == 200
    body = response.json()
    assert body["today"]["ceilingUsd"] > 0
    assert body["today"]["phase"]
    assert len(body["calendar"]) > 30
    assert body["calendar"][0]["date"] < body["calendar"][-1]["date"]
