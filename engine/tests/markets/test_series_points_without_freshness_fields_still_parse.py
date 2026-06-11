from __future__ import annotations

import json

from wolves.markets.series import SeriesPoint

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
