from __future__ import annotations

from tests.fakes import build_test_app, client_for, published_engine


async def test_paths_serve_both_views_for_a_known_team(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        reach = (await client.get("/teams/england/paths")).json()
        title = (await client.get("/teams/england/paths", params={"view": "title"})).json()

    assert reach["team"] == "england"
    assert reach["view"] == "reach"
    assert 0.0 < reach["p_champion"] < 1.0
    assert {s["stage"] for s in reach["stages"]} == {"r32", "r16", "qf", "sf", "final"}
    assert title["view"] == "title"
    assert title["stages"][-1]["p_play"] == 1.0


async def test_unknown_team_is_404(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/teams/narnia/paths")

    assert response.status_code == 404
