from __future__ import annotations

import json
from pathlib import Path

from wolves.markets.series import SeriesPoint, load_series

OLD_POINT = {
    "captured_at": "2026-06-01T10:00:00+00:00",
    "outright_bookmakers": {"england": 0.12},
    "outright_polymarket": {"england": 0.11},
    "matches": [
        {
            "home": "england",
            "away": "croatia",
            "commence_at": "2026-06-17T20:00:00+00:00",
            "p_home": 0.55,
            "p_draw": 0.25,
            "p_away": 0.2,
        }
    ],
}


def test_pre_freshness_points_parse_with_none_defaults() -> None:
    point = SeriesPoint.model_validate_json(json.dumps(OLD_POINT))
    assert point.outright_updated_oldest is None
    assert point.outright_updated_newest is None
    assert point.matches[0].last_update is None


def test_invalid_series_point_does_not_hide_valid_history(tmp_path: Path) -> None:
    day = tmp_path / "2026-06-01"
    day.mkdir()
    (day / "100000.series.json").write_text("{}", encoding="utf-8")
    (day / "110000.series.json").write_text(json.dumps(OLD_POINT), encoding="utf-8")

    points = load_series(tmp_path)

    assert [point.captured_at for point in points] == [OLD_POINT["captured_at"]]
