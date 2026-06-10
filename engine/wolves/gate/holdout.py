"""Frozen temporal holdout: every odds-covered tournament match, labelled and
joined orientation-safely to its market consensus. The splits never change;
challengers fitted on data past a fold's start date are refused upstream."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
import numpy as np

from wolves.markets.devig import consensus_probabilities, power_devig
from wolves.models.contracts import DatasetHandle

# Whole tournaments, scored with a single leak-free fit as_of the fold start.
TOURNAMENT_FOLDS: tuple[tuple[str, date], ...] = (
    ("World Cup 2014", date(2014, 6, 12)),
    ("Euro 2016", date(2016, 6, 10)),
    ("Copa América", date(2016, 6, 3)),
    ("Africa Cup of Nations 2017", date(2017, 1, 14)),
    ("FIFA Confederations Cup", date(2017, 6, 17)),
    ("Gold Cup", date(2017, 7, 7)),
    ("World Cup 2018", date(2018, 6, 14)),
    ("World Cup 2022", date(2022, 11, 20)),
)


@dataclass(frozen=True)
class HoldoutMatch:
    fold: str
    fit_as_of: date
    date: date
    home_team: str
    away_team: str
    neutral: bool
    outcome: int
    market: np.ndarray


def _outcome(home_goals: int, away_goals: int, *, went_to_shootout: bool) -> int:
    if went_to_shootout or home_goals == away_goals:
        return 1
    return 0 if home_goals > away_goals else 2


def _consensus(trios: list[tuple[float, float, float]]) -> np.ndarray:
    per_book = []
    for home, draw, away in trios:
        devigged = power_devig([home, draw, away])
        per_book.append({"home": devigged[0], "draw": devigged[1], "away": devigged[2]})
    consensus = consensus_probabilities(per_book)
    return np.array([consensus["home"], consensus["draw"], consensus["away"]])


def load_holdout(dataset: DatasetHandle) -> list[HoldoutMatch]:
    connection = duckdb.connect(str(dataset.path), read_only=True)
    try:
        odds_rows = connection.execute(
            "select competition, date, home_team, away_team, home_goals, away_goals,"
            " list(row(home_price, draw_price, away_price))"
            " from match_odds group by 1, 2, 3, 4, 5, 6"
        ).fetchall()
        close_rows = connection.execute(
            "select home_team, away_team, list(row(home_price, draw_price, away_price)) from wc2022_closes"
            " group by 1, 2"
        ).fetchall()
        wc2022_results = connection.execute(
            "select date, home_team, away_team, home_goals, away_goals, neutral from matches"
            " where tournament = 'FIFA World Cup' and date between '2022-11-20' and '2022-12-18'"
        ).fetchall()
        shootouts = {
            (played, frozenset((home, away)))
            for played, home, away in connection.execute("select date, home_team, away_team from shootouts").fetchall()
        }
    finally:
        connection.close()

    folds = dict(TOURNAMENT_FOLDS)
    matches: list[HoldoutMatch] = []
    for competition, played, home, away, home_goals, away_goals, trios in odds_rows:
        if competition not in folds:
            continue
        # football-data scores are 90-minute full time, so no shootout correction.
        matches.append(
            HoldoutMatch(
                fold=competition,
                fit_as_of=folds[competition],
                date=played,
                home_team=home,
                away_team=away,
                neutral=True,
                outcome=_outcome(home_goals, away_goals, went_to_shootout=False),
                market=_consensus(trios),
            )
        )

    # The Odds API sometimes flips home/away relative to the FIFA listing.
    closes = {frozenset((home, away)): (home, list(trios)) for home, away, trios in close_rows}
    for played, home, away, home_goals, away_goals, neutral in wc2022_results:
        entry = closes.get(frozenset((home, away)))
        if entry is None:
            continue
        listed_home, trios = entry
        oriented = trios if listed_home == home else [(a, d, h) for h, d, a in trios]
        # martj42 scores include extra time; a shootout means level at 90 and 120.
        went_to_shootout = (played, frozenset((home, away))) in shootouts
        matches.append(
            HoldoutMatch(
                fold="World Cup 2022",
                fit_as_of=folds["World Cup 2022"],
                date=played,
                home_team=home,
                away_team=away,
                neutral=bool(neutral),
                outcome=_outcome(home_goals, away_goals, went_to_shootout=went_to_shootout),
                market=_consensus(oriented),
            )
        )
    return sorted(matches, key=lambda m: (m.fit_as_of, m.date))
