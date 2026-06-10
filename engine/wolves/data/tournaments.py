"""Historical tournaments with purchasable closing odds. One registry shared
by the pull script, the dataset builder and the gate holdout, so a tournament
is added in exactly one place."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ClosesTournament:
    slug: str
    fold: str
    odds_sport_key: str
    api_football_league: int
    api_football_season: int
    results_tournament: str
    first_match: date
    last_match: date

    @property
    def fit_as_of(self) -> date:
        return self.first_match


CLOSES_TOURNAMENTS: tuple[ClosesTournament, ...] = (
    ClosesTournament(
        slug="euro2020",
        fold="Euro 2020",
        odds_sport_key="soccer_uefa_european_championship",
        api_football_league=4,
        api_football_season=2020,
        results_tournament="UEFA Euro",
        first_match=date(2021, 6, 11),
        last_match=date(2021, 7, 11),
    ),
    ClosesTournament(
        slug="wc2022",
        fold="World Cup 2022",
        odds_sport_key="soccer_fifa_world_cup",
        api_football_league=1,
        api_football_season=2022,
        results_tournament="FIFA World Cup",
        first_match=date(2022, 11, 20),
        last_match=date(2022, 12, 18),
    ),
    ClosesTournament(
        slug="afcon2023",
        fold="AFCON 2023",
        odds_sport_key="soccer_africa_cup_of_nations",
        api_football_league=6,
        api_football_season=2023,
        results_tournament="African Cup of Nations",
        first_match=date(2024, 1, 13),
        last_match=date(2024, 2, 11),
    ),
    ClosesTournament(
        slug="euro2024",
        fold="Euro 2024",
        odds_sport_key="soccer_uefa_european_championship",
        api_football_league=4,
        api_football_season=2024,
        results_tournament="UEFA Euro",
        first_match=date(2024, 6, 14),
        last_match=date(2024, 7, 14),
    ),
    ClosesTournament(
        slug="copa2024",
        fold="Copa America 2024",
        odds_sport_key="soccer_conmebol_copa_america",
        api_football_league=9,
        api_football_season=2024,
        results_tournament="Copa América",
        first_match=date(2024, 6, 20),
        last_match=date(2024, 7, 14),
    ),
)
