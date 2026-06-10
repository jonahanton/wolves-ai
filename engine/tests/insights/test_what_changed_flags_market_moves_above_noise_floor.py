from __future__ import annotations

from pathlib import Path

from wolves.insights.market import moves_between
from wolves.markets.series import SeriesPoint


def _write_point(archive_dir: Path, day: str, time: str, bookmakers: dict[str, float]) -> None:
    point = SeriesPoint(
        captured_at=f"{day}T{time}+00:00",
        outright_bookmakers=bookmakers,
        outright_polymarket={},
        matches=[],
    )
    day_dir = archive_dir / day
    day_dir.mkdir(exist_ok=True)
    (day_dir / f"{time.replace(':', '')}.series.json").write_text(point.model_dump_json(), encoding="utf-8")


def test_moves_above_floor_appear_and_below_floor_do_not(tmp_path: Path) -> None:
    _write_point(tmp_path, "2026-06-09", "08:00:00", {"england": 0.10, "spain": 0.050})
    _write_point(tmp_path, "2026-06-10", "07:00:00", {"england": 0.12, "spain": 0.052})

    moves = moves_between(tmp_path, since="2026-06-09T09:00:00+00:00", floor_pp=0.7)

    assert moves == {"england": 2.0}


def test_no_snapshot_since_previous_run_means_no_moves(tmp_path: Path) -> None:
    _write_point(tmp_path, "2026-06-09", "08:00:00", {"england": 0.10})
    _write_point(tmp_path, "2026-06-10", "07:00:00", {"england": 0.12})

    assert moves_between(tmp_path, since="2026-06-10T09:00:00+00:00", floor_pp=0.7) == {}
