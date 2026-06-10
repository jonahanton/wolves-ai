"""Frozen temporal holdout: every odds-covered tournament match, labelled and
joined orientation-safely to its market consensus. The splits never change;
challengers fitted on data past a fold's start date are refused upstream."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import duckdb
import numpy as np

from wolves.data.tournaments import CLOSES_TOURNAMENTS
from wolves.markets.devig import consensus_probabilities, power_devig
from wolves.models.contracts import DatasetHandle

# football-data workbook competitions, scored with one leak-free fit per fold.
WORKBOOK_FOLDS: tuple[tuple[str, date], ...] = (
    ("World Cup 2014", date(2014, 6, 12)),
    ("Euro 2016", date(2016, 6, 10)),
    ("Copa América", date(2016, 6, 3)),
    ("Africa Cup of Nations 2017", date(2017, 1, 14)),
    ("FIFA Confederations Cup", date(2017, 6, 17)),
    ("Gold Cup", date(2017, 7, 7)),
    ("World Cup 2018", date(2018, 6, 14)),
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
        workbook_rows = connection.execute(
            "select competition, date, home_team, away_team,"
            " list(row(home_price, draw_price, away_price))"
            " from match_odds where bookmaker != 'market-max' group by 1, 2, 3, 4"
        ).fetchall()
        all_results = connection.execute(
            "select date, home_team, away_team, home_goals, away_goals from matches where date >= '2014-01-01'"
        ).fetchall()
        close_rows = connection.execute(
            "select tournament, home_team, away_team, cast(commence_at as date),"
            " list(row(home_price, draw_price, away_price))"
            " from market_closes group by 1, 2, 3, 4"
        ).fetchall()
        results_by_slug = {
            t.slug: connection.execute(
                "select date, home_team, away_team, home_goals, away_goals, neutral from matches"
                " where tournament = ? and date between ? and ?",
                [t.results_tournament, t.first_match.isoformat(), t.last_match.isoformat()],
            ).fetchall()
            for t in CLOSES_TOURNAMENTS
        }
        shootouts = {
            (played, frozenset((home, away)))
            for played, home, away in connection.execute("select date, home_team, away_team from shootouts").fetchall()
        }
    finally:
        connection.close()

    # Workbook full-time scores encode shootout winners as one-goal wins, so
    # outcome labels come from the results backbone, never from the workbook.
    results_index: dict[frozenset[str], list[tuple[date, str, int, int]]] = {}
    for played, home, away, home_goals, away_goals in all_results:
        results_index.setdefault(frozenset((home, away)), []).append((played, home, home_goals, away_goals))

    matches: list[HoldoutMatch] = []
    workbook_folds = dict(WORKBOOK_FOLDS)
    for competition, played, home, away, trios in workbook_rows:
        if competition not in workbook_folds:
            continue
        candidates = results_index.get(frozenset((home, away)), [])
        if not candidates:
            continue
        result_date, result_home, home_goals, away_goals = min(candidates, key=lambda c: abs((c[0] - played).days))
        if abs((result_date - played).days) > 1:
            continue
        if result_home != home:
            home_goals, away_goals = away_goals, home_goals
        went_to_shootout = (result_date, frozenset((home, away))) in shootouts
        matches.append(
            HoldoutMatch(
                fold=competition,
                fit_as_of=workbook_folds[competition],
                date=played,
                home_team=home,
                away_team=away,
                neutral=True,
                outcome=_outcome(home_goals, away_goals, went_to_shootout=went_to_shootout),
                market=_consensus(trios),
            )
        )

    # The Odds API sometimes flips home/away relative to the FIFA listing, and a
    # pair can meet twice in one tournament, so the join is by pair AND nearest date.
    closes: dict[tuple[str, frozenset[str]], list[tuple[date, str, list]]] = {}
    for tournament_slug, home, away, commence, trios in close_rows:
        closes.setdefault((tournament_slug, frozenset((home, away))), []).append((commence, home, list(trios)))
    for tournament in CLOSES_TOURNAMENTS:
        for played, home, away, home_goals, away_goals, neutral in results_by_slug[tournament.slug]:
            entries = closes.get((tournament.slug, frozenset((home, away))))
            if not entries:
                continue
            commence, listed_home, trios = min(entries, key=lambda e: abs((e[0] - played).days))
            if abs((commence - played).days) > 1:
                continue
            oriented = trios if listed_home == home else [(a, d, h) for h, d, a in trios]
            # martj42 scores include extra time; a shootout means level at 90 and 120.
            went_to_shootout = (played, frozenset((home, away))) in shootouts
            matches.append(
                HoldoutMatch(
                    fold=tournament.fold,
                    fit_as_of=tournament.fit_as_of,
                    date=played,
                    home_team=home,
                    away_team=away,
                    neutral=bool(neutral),
                    outcome=_outcome(home_goals, away_goals, went_to_shootout=went_to_shootout),
                    market=_consensus(oriented),
                )
            )
    return sorted(matches, key=lambda m: (m.fit_as_of, m.date))
