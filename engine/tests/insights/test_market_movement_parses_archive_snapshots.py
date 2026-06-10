from __future__ import annotations

import json

import pytest

from wolves.config import get_settings
from wolves.insights.market import market_movement
from wolves.sim.format import load_format

FMT = load_format(get_settings().data_dir)


def _snapshot(captured_at: str, england_price: float, draw_price: float) -> dict:
    outright = {
        "id": "o",
        "sport_key": "soccer_fifa_world_cup_winner",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "markets": [
                    {
                        "key": "outrights",
                        "outcomes": [{"name": "England", "price": england_price}, {"name": "Spain", "price": 5.0}],
                    }
                ],
            }
        ],
    }
    h2h = {
        "id": "m",
        "sport_key": "soccer_fifa_world_cup",
        "commence_time": "2026-06-17T20:00:00Z",
        "home_team": "England",
        "away_team": "Croatia",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "England", "price": 1.6},
                            {"name": "Draw", "price": draw_price},
                            {"name": "Croatia", "price": 6.0},
                        ],
                    }
                ],
            }
        ],
    }
    polymarket = [{"markets": [{"question": "Will England win the World Cup?", "outcomePrices": '["0.10"]'}]}]
    return {
        "captured_at": captured_at,
        "engine_version": "0",
        "sources": {
            "odds_outrights": {"payload": [outright]},
            "odds_h2h": {"payload": [h2h]},
            "polymarket": {"payload": polymarket},
        },
    }


def test_series_deltas_and_h2h_tracking(tmp_path) -> None:
    day = tmp_path / "2026-06-17"
    day.mkdir()
    (day / "100000.json").write_text(json.dumps(_snapshot("2026-06-17T10:00:00+00:00", 8.0, 4.0)), encoding="utf-8")
    (day / "180000.json").write_text(json.dumps(_snapshot("2026-06-17T18:00:00+00:00", 6.0, 4.2)), encoding="utf-8")

    movement = market_movement(tmp_path, FMT)

    england = next(m for m in movement.outright_bookmakers if m.team == "england")
    assert len(england.history) == 2
    assert england.delta_pp_vs_previous > 0
    assert england.delta_pp_vs_previous == england.delta_pp_vs_oldest

    assert len(movement.outright_polymarket) >= 1
    match = movement.matches[0]
    assert (match.home, match.away) == ("england", "croatia")
    assert match.previous is not None
    assert match.max_move_pp > 0
    assert sum(match.current.values()) == pytest.approx(1.0, abs=0.01)
