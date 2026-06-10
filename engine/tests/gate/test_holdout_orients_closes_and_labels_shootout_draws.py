from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from wolves.data.build import write_dataset
from wolves.gate.holdout import load_holdout
from wolves.models.contracts import DatasetHandle


@pytest.fixture()
def dataset(tmp_path) -> DatasetHandle:
    matches = pd.DataFrame(
        [
            # The final: 3-3 after extra time, decided on penalties; martj42 lists argentina at home.
            {
                "date": date(2022, 12, 18),
                "home_team": "argentina",
                "away_team": "france",
                "home_goals": 3,
                "away_goals": 3,
                "tournament": "FIFA World Cup",
                "importance": 4.0,
                "neutral": True,
            },
            {
                "date": date(2022, 12, 13),
                "home_team": "argentina",
                "away_team": "croatia",
                "home_goals": 3,
                "away_goals": 0,
                "tournament": "FIFA World Cup",
                "importance": 4.0,
                "neutral": True,
            },
        ]
    )
    shootouts = pd.DataFrame(
        [{"date": date(2022, 12, 18), "home_team": "argentina", "away_team": "france", "winner": "argentina"}]
    )
    # The Odds API listed the final with france at home: prices must flip on join.
    closes = pd.DataFrame(
        [
            {
                "snapshot_at": datetime(2022, 12, 18, 14, 50),
                "commence_at": datetime(2022, 12, 18, 15, 0),
                "home_team": "france",
                "away_team": "argentina",
                "bookmaker": "pinnacle",
                "home_price": 3.05,
                "draw_price": 3.1,
                "away_price": 2.6,
            }
        ]
    )
    match_odds = pd.DataFrame(
        [
            {
                "competition": "World Cup 2014",
                "date": date(2014, 6, 12),
                "home_team": "brazil",
                "away_team": "croatia",
                "home_goals": 3,
                "away_goals": 1,
                "bookmaker": "bet365",
                "home_price": 1.25,
                "draw_price": 6.0,
                "away_price": 12.0,
            }
        ]
    )
    out = tmp_path
    write_dataset(
        out,
        version="t",
        tables={"matches": matches, "shootouts": shootouts, "wc2022_closes": closes, "match_odds": match_odds},
        hashes={},
    )
    return DatasetHandle(path=out / "wolves-data-t.duckdb", version="t")


def test_flipped_closes_reorient_and_shootouts_label_as_draws(dataset) -> None:
    holdout = load_holdout(dataset)
    final = next(m for m in holdout if m.fold == "World Cup 2022")

    assert (final.home_team, final.away_team) == ("argentina", "france")
    assert final.outcome == 1
    # Argentina's de-vigged probability must exceed France's after reorientation.
    assert final.market[0] > final.market[2]


def test_football_data_rows_join_without_shootout_correction(dataset) -> None:
    wc2014 = next(m for m in load_holdout(dataset) if m.fold == "World Cup 2014")
    assert wc2014.outcome == 0
    assert wc2014.fit_as_of == date(2014, 6, 12)
