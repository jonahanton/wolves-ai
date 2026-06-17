from __future__ import annotations

from tests.fakes import build_test_app, client_for, published_engine


async def test_group_fixture_grid_is_a_normalised_distribution(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    spec = engine.forecaster.fmt.group_matches[0]
    async with client_for(app) as client:
        response = await client.get(f"/matches/{spec.match}/grid")

    assert response.status_code == 200
    body = response.json()
    assert body["homeId"] == spec.home
    assert body["awayId"] == spec.away
    assert body["stage"] == "group"
    assert 0.99 < sum(sum(row) for row in body["grid"]) < 1.01
    assert 0.99 < body["pHome"] + body["pDraw"] + body["pAway"] < 1.01


async def test_unknown_match_is_404_and_unresolved_knockout_is_409(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    knockout = engine.forecaster.fmt.knockout[0].match
    async with client_for(app) as client:
        missing = await client.get("/matches/9999/grid")
        unresolved = await client.get(f"/matches/{knockout}/grid")

    assert missing.status_code == 404
    assert unresolved.status_code == 409
