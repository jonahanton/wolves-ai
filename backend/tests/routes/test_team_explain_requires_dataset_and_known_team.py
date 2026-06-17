from __future__ import annotations

from tests.fakes import build_test_app, client_for, published_engine


async def test_explain_degrades_to_503_without_the_research_dataset(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        missing_dataset = await client.get("/teams/england/explain")
        unknown_team = await client.get("/teams/narnia/explain")

    assert missing_dataset.status_code == 503
    assert unknown_team.status_code == 404
