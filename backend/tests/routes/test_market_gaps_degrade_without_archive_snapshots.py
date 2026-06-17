from __future__ import annotations

from tests.fakes import build_test_app, client_for, published_engine


async def test_gaps_table_serves_model_probabilities_with_no_market_legs(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/market/gaps")

    assert response.status_code == 200
    body = response.json()
    assert body["as_of"] == "no market snapshots held"
    assert body["gaps"]
    top = body["gaps"][0]
    assert 0.0 < top["model_p_title"] <= 1.0
    assert top["market_p_title"] is None
    assert top["gap_pp"] is None
