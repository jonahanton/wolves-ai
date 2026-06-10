from __future__ import annotations

import json

from wolves.data.sources.wc2022_closes import load_closes

H2H_SNAPSHOT = {
    "timestamp": "2022-12-18T14:50:38Z",
    "data": [
        {
            "commence_time": "2022-12-18T15:00:00Z",
            "home_team": "Argentina",
            "away_team": "France",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Argentina", "price": 2.6},
                                {"name": "France", "price": 3.05},
                                {"name": "Draw", "price": 3.1},
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "commence_time": "2022-12-19T15:00:00Z",
            "home_team": "Ghost",
            "away_team": "Match",
            "bookmakers": [],
        },
    ],
}

OUTRIGHT_SNAPSHOT = {
    "timestamp": "2022-11-20T15:50:00Z",
    "data": [
        {
            "commence_time": "2022-11-20T16:00:00Z",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "markets": [{"key": "outrights", "outcomes": [{"name": "Brazil", "price": 4.2}]}],
                }
            ],
        }
    ],
}


def test_window_filter_and_outcome_mapping(tmp_path) -> None:
    (tmp_path / "h2h-20221218T1455Z.json").write_text(json.dumps(H2H_SNAPSHOT), encoding="utf-8")
    (tmp_path / "outrights-close.json").write_text(json.dumps(OUTRIGHT_SNAPSHOT), encoding="utf-8")

    closes, outrights = load_closes(tmp_path)

    assert len(closes) == 1
    close = closes[0]
    assert (close.home_team, close.away_team, close.bookmaker) == ("argentina", "france", "pinnacle")
    assert (close.home_price, close.draw_price, close.away_price) == (2.6, 3.1, 3.05)
    assert [(o.team, o.price) for o in outrights] == [("brazil", 4.2)]


def test_absent_directory_yields_empty_tables(tmp_path) -> None:
    assert load_closes(tmp_path / "missing") == ([], [])
