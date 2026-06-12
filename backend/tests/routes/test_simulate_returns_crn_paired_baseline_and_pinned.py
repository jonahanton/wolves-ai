from __future__ import annotations

from tests.fakes import build_test_app, client_for, published_engine
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import PlayedResult
from wolves.sim.results_store import ResultsStore

N_SIMS = 2000


async def test_no_pins_returns_identical_baseline_and_pinned(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.post("/simulate", json={"nSims": N_SIMS})

    assert response.status_code == 200
    body = response.json()
    assert body["engine"]["fittedRunId"] == "run-test"
    assert body["pinned"] == body["baseline"]
    assert 0.99 < sum(team["champion"] for team in body["baseline"].values()) < 1.01


async def test_pinned_thrashing_moves_reach_while_baseline_is_stable(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    pin = {"match": 1, "homeGoals": 9, "awayGoals": 0}
    async with client_for(app) as client:
        unpinned = (await client.post("/simulate", json={"nSims": N_SIMS})).json()
        pinned = (await client.post("/simulate", json={"nSims": N_SIMS, "pins": [pin]})).json()

    assert pinned["baseline"] == unpinned["baseline"]
    home = engine.forecaster.fmt.group_matches[0].home
    assert pinned["pinned"][home]["r32"] > pinned["baseline"][home]["r32"]


async def test_pinning_a_played_match_conflicts(tmp_path):
    engine = published_engine(tmp_path)
    ResultsStore(ArtifactStore(engine._settings)).record({1: PlayedResult(match=1, home_goals=2, away_goals=0)})
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.post(
            "/simulate", json={"nSims": N_SIMS, "pins": [{"match": 1, "homeGoals": 1, "awayGoals": 1}]}
        )

    assert response.status_code == 409


async def test_simulate_is_unavailable_before_the_engine_boots(tmp_path):
    app = build_test_app(storage_dir=tmp_path)
    async with client_for(app) as client:
        response = await client.post("/simulate", json={})

    assert response.status_code == 503


async def test_pin_payloads_are_capped(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    pins = [{"match": m, "homeGoals": 1, "awayGoals": 0} for m in range(1, 11)]
    async with client_for(app) as client:
        too_many = await client.post("/simulate", json={"pins": pins})
        silly_score = await client.post("/simulate", json={"pins": [{"match": 1, "homeGoals": 12, "awayGoals": 0}]})

    assert too_many.status_code == 400
    assert silly_score.status_code == 400
