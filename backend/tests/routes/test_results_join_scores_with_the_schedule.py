from __future__ import annotations

from tests.fakes import build_test_app, client_for, published_engine
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import PlayedResult
from wolves.sim.results_store import ResultsStore


async def test_results_serve_scores_with_schedule_dates_and_teams(tmp_path):
    engine = published_engine(tmp_path)
    ResultsStore(ArtifactStore(engine.settings)).record(
        {
            1: PlayedResult(match=1, home_goals=2, away_goals=0),
            2: PlayedResult(match=2, home_goals=1, away_goals=1),
        }
    )
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/results")

    assert response.status_code == 200
    rows = response.json()["results"]
    fmt = engine.forecaster.fmt
    schedule = {m.match: m for m in fmt.group_matches}
    assert {row["match"] for row in rows} == {1, 2}
    first = next(row for row in rows if row["match"] == 1)
    assert first["homeId"] == schedule[1].home
    assert first["awayId"] == schedule[1].away
    assert first["date"] == schedule[1].date
    assert first["stage"] == "group"
    assert (first["homeGoals"], first["awayGoals"]) == (2, 0)
    assert rows == sorted(rows, key=lambda row: (row["date"], row["match"]), reverse=True)


async def test_results_empty_before_any_match(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/results")

    assert response.status_code == 200
    assert response.json() == {"results": []}
