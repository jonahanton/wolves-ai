from __future__ import annotations

from pathlib import Path

from wolves.insights.market_gaps import market_gaps
from wolves.markets.series import SeriesPoint


def _write_point(archive: Path, stamp: str, bookmakers: dict[str, float]) -> None:
    day = archive / stamp[:10]
    day.mkdir(parents=True, exist_ok=True)
    point = SeriesPoint(captured_at=stamp, outright_bookmakers=bookmakers, outright_polymarket={}, matches=[])
    (day / f"outright-{stamp.replace(':', '')}.series.json").write_text(point.model_dump_json(), encoding="utf-8")


def test_gap_table_reads_newest_snapshot_with_prices(forecaster, tmp_path: Path):
    archive = tmp_path / "odds-archive"
    teams = [t.id for t in forecaster.fmt.teams[:2]]
    _write_point(archive, "2026-06-10T10:00:00+00:00", {teams[0]: 0.4, teams[1]: 0.3})
    _write_point(archive, "2026-06-10T15:00:00+00:00", {})

    table = market_gaps(forecaster, archive, n_sims=2_000, seed=0)

    priced = {g.team: g.market_p_title for g in table.gaps if g.market_p_title is not None}
    assert priced == {teams[0]: 0.4, teams[1]: 0.3}


def test_gap_table_prefers_current_market_prices(forecaster, tmp_path: Path):
    archive = tmp_path / "odds-archive"
    teams = [t.id for t in forecaster.fmt.teams[:2]]
    _write_point(archive, "2026-06-10T10:00:00+00:00", {teams[0]: 0.4, teams[1]: 0.3})

    table = market_gaps(
        forecaster,
        archive,
        current_market={teams[0]: 0.2, teams[1]: 0.5},
        current_polymarket={teams[0]: 0.25},
        current_as_of="2026-06-14T15:36:00+00:00",
        n_sims=2_000,
        seed=0,
    )

    by_team = {g.team: g for g in table.gaps}
    assert table.as_of == "2026-06-14T15:36:00+00:00"
    assert by_team[teams[0]].market_p_title == 0.2
    assert by_team[teams[0]].polymarket_p_title == 0.25
