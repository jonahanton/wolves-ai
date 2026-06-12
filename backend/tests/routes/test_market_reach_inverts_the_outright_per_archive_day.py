from __future__ import annotations

import json

from tests.fakes import build_test_app, client_for, published_engine
from wolves.markets.inverse import title_probabilities
from wolves.markets.series import SeriesPoint

STAGE_ORDER = ("r32", "r16", "qf", "sf", "final", "champion")


def tilted_outright(engine) -> tuple[dict[str, float], str]:
    """The engine's own outright with the favourite boosted: full coverage, mild disagreement."""
    base = title_probabilities(engine.forecaster.fmt, engine.forecaster.state, seed=0, n_sims=2000)
    favourite = max(base, key=lambda team: base[team])
    tilted = {team: p * (1.4 if team == favourite else 1.0) for team, p in base.items()}
    total = sum(tilted.values())
    return {team: p / total for team, p in tilted.items()}, favourite


def write_capture(runs_root, day: str, time: str, outright: dict[str, float]) -> None:
    point = SeriesPoint(
        captured_at=f"{day}T{time}+00:00", outright_bookmakers=outright, outright_polymarket={}, matches=[]
    )
    directory = runs_root / "odds-archive" / day
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{time.replace(':', '')}.series.json").write_text(point.model_dump_json(), encoding="utf-8")


async def test_reach_serves_implied_stage_probabilities_and_persists_them(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    outright, favourite = tilted_outright(engine)
    write_capture(tmp_path, "2026-06-10", "08:00:00", outright)
    write_capture(tmp_path, "2026-06-10", "14:00:00", outright)
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/market/reach")

    assert response.status_code == 200
    points = response.json()["points"]
    assert [p["date"] for p in points] == ["2026-06-10"]
    point = points[0]
    assert point["captured_at"] == "2026-06-10T14:00:00+00:00"
    assert point["outright"] == outright
    reach = point["teams"][favourite]
    assert all(reach[a] >= reach[b] for a, b in zip(STAGE_ORDER, STAGE_ORDER[1:], strict=False))
    assert abs(reach["champion"] - outright[favourite]) < 0.05

    persisted = tmp_path / "odds-archive" / "2026-06-10" / "implied-reach.json"
    assert json.loads(persisted.read_text())["captured_at"] == "2026-06-10T14:00:00+00:00"


async def test_reach_degrades_to_404_without_archive_snapshots(tmp_path):
    engine = published_engine(tmp_path)
    await engine.boot()
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        response = await client.get("/market/reach")

    assert response.status_code == 404
