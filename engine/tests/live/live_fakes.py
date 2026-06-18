from __future__ import annotations

from datetime import datetime

from wolves.clients.api_football import MatchFixture
from wolves.config import Settings
from wolves.models.contracts import ScorelineDistribution
from wolves.sim.format import load_format


def live_fixture(
    home: str = "Mexico",
    away: str = "South Africa",
    *,
    fixture_id: int = 1300001,
    day: str = "2026-06-11T19:00:00+00:00",
    status: str = "live",
    goals: tuple[int | None, int | None] = (0, 0),
    elapsed: int | None = 60,
) -> MatchFixture:
    return MatchFixture(
        fixture_id=fixture_id,
        kickoff=datetime.fromisoformat(day),
        status=status,
        home=home,
        away=away,
        home_goals=goals[0],
        away_goals=goals[1],
        elapsed=elapsed,
        city="Mexico City",
    )


class FakeLiveForecaster:
    def __init__(self) -> None:
        self.fmt = load_format(Settings().data_dir)
        self._fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, *, as_of=None, extra_results=None):
        self._fitted = True
        return None

    def match_probs(self, home: str, away: str, *, neutral: bool = True, match: int | None = None):
        return {"home": 0.45, "draw": 0.28, "away": 0.27}

    def score_grid(self, home: str, away: str, *, neutral: bool = True, match: int | None = None):
        return ScorelineDistribution.single(1, 1)

    def live_match(self, home: str, away: str, state, *, knockout: bool, signals=None):
        if state.home_goals > state.away_goals:
            return {"home": 0.78, "draw": 0.15, "away": 0.07}
        return {"home": 0.40, "draw": 0.31, "away": 0.29}

    def live_distribution(self, home: str, away: str, state, *, signals=None):
        return ScorelineDistribution.single(state.home_goals, state.away_goals)

    def title_probs(self, *, n_sims: int, seed: int = 0, results=None, live_distributions=None):
        dist = (live_distributions or {})[1]
        return {"mexico": 0.18 + 0.04 * dist.p_home, "south_africa": 0.06 + 0.03 * dist.p_away}
