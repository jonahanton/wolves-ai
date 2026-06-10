"""Match engines: the pluggable core of the tournament Monte Carlo. The
bracket, group ranking and tie-break logic in mc.py is engine-agnostic; an
engine owns team strength state, goal-rate maths and knockout resolution."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from wolves.sim.elo import rating_delta
from wolves.sim.format import FormatData
from wolves.sim.match import STAGE_GAP_MULT, goal_means, knockout_home_wins, simulate_goals
from wolves.sim.venues import venue_bonus_table

RATING_SIGMA = 35.0


class MatchEngine(Protocol):
    def begin(self, rng: np.random.Generator, n_sims: int) -> None: ...

    def lambdas(
        self, home: np.ndarray, away: np.ndarray, *, city: str, stage: str
    ) -> tuple[np.ndarray, np.ndarray]: ...

    def simulate_goals(
        self, rng: np.random.Generator, lam_home: np.ndarray, lam_away: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]: ...

    def knockout_home_wins(
        self, rng: np.random.Generator, home: np.ndarray, away: np.ndarray, hg: np.ndarray, ag: np.ndarray, *, city: str
    ) -> np.ndarray: ...

    def record_result(
        self,
        home: np.ndarray,
        away: np.ndarray,
        hg: np.ndarray,
        ag: np.ndarray,
        home_wins: np.ndarray,
        *,
        city: str,
        stage: str,
    ) -> None: ...


class EloMatchEngine:
    """The original engine: Elo with venue bonuses, stage gap multipliers,
    correlated over-dispersed goals and hot in-sim rating updates."""

    def __init__(self, fmt: FormatData, base_ratings: np.ndarray, *, rating_sigma: float = RATING_SIGMA) -> None:
        self._base = base_ratings
        self._sigma = rating_sigma
        self._bonus = venue_bonus_table(fmt)
        self._ratings = np.empty(0)
        self._sims = np.empty(0, dtype=np.intp)

    def begin(self, rng: np.random.Generator, n_sims: int) -> None:
        self._ratings = self._base[:, None] + rng.normal(0.0, self._sigma, (self._base.shape[0], n_sims))
        self._sims = np.arange(n_sims)

    def _diff(self, home: np.ndarray, away: np.ndarray, *, city: str, stage: str) -> np.ndarray:
        return STAGE_GAP_MULT[stage] * (self._ratings[home, self._sims] - self._ratings[away, self._sims]) + (
            self._bonus[city][home] - self._bonus[city][away]
        )

    def lambdas(self, home: np.ndarray, away: np.ndarray, *, city: str, stage: str) -> tuple[np.ndarray, np.ndarray]:
        return goal_means(self._diff(home, away, city=city, stage=stage))

    def simulate_goals(
        self, rng: np.random.Generator, lam_home: np.ndarray, lam_away: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        return simulate_goals(rng, lam_home, lam_away)

    def knockout_home_wins(
        self, rng: np.random.Generator, home: np.ndarray, away: np.ndarray, hg: np.ndarray, ag: np.ndarray, *, city: str
    ) -> np.ndarray:
        return knockout_home_wins(rng, self._diff(home, away, city=city, stage="knockout"), hg, ag)

    def record_result(
        self,
        home: np.ndarray,
        away: np.ndarray,
        hg: np.ndarray,
        ag: np.ndarray,
        home_wins: np.ndarray,
        *,
        city: str,
        stage: str,
    ) -> None:
        diff = self._diff(home, away, city=city, stage=stage)
        if stage == "knockout":
            # eloratings.net scores shootout wins as one-goal wins, so the hot update mirrors that.
            level = hg == ag
            hg = np.where(level, hg + home_wins, hg)
            ag = np.where(level, ag + ~home_wins, ag)
        delta = rating_delta(diff, hg, ag, stage=stage)
        self._ratings[home, self._sims] += delta
        self._ratings[away, self._sims] -= delta
