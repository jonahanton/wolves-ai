"""In-match model: final-score distribution conditional on minute, score and
red cards. A deterministic Markov chain over scoreline states in one-minute
steps (no Monte Carlo), with a half-stepped intensity profile, the post-2022
FIFA stoppage regime, score-state multipliers and a flat extra-time rate.
Fitted constants come from WC 1986-2022 goal timings via
scripts/fit_inmatch_hazard.py."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise

import numpy as np

from wolves.models.contracts import MAX_GOALS, ScorelineDistribution

H1_MINUTES = 45.0
H2_MINUTES = 45.0
ET_MINUTES = 33.0


@dataclass(frozen=True)
class HazardParams:
    """Multiplicative hazard constants; profile holds per-minute intensities
    for minutes 0-90 with mean 1 over regulation."""

    profile: tuple[float, ...]
    h1_stoppage_intensity: float
    level: float
    trailing_one: float
    trailing_two: float
    leading: float
    red_sanctioned: float
    red_opponent: float
    h1_stoppage: float
    h2_stoppage_close: float
    h2_stoppage_settled: float


def _linear_profile(knots: tuple[tuple[float, float], ...]) -> tuple[float, ...]:
    def at(minute: float) -> float:
        if minute >= knots[-1][0]:
            return knots[-1][1]
        for (m0, v0), (m1, v1) in pairwise(knots):
            if m0 <= minute <= m1:
                return v0 + (v1 - v0) * (minute - m0) / (m1 - m0)
        return knots[0][1]

    return tuple(at(float(m)) for m in range(91))


def _step_profile(bins: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(bins[min(m // 15, 5)] for m in range(91))


INCUMBENT = HazardParams(
    profile=_linear_profile(((0.0, 0.85), (45.0, 1.05), (45.001, 1.05), (90.0, 1.45))),
    h1_stoppage_intensity=1.05,
    level=1.0,
    trailing_one=1.10,
    trailing_two=1.20,
    leading=0.90,
    red_sanctioned=0.60,
    red_opponent=1.50,
    h1_stoppage=4.0,
    h2_stoppage_close=9.0,
    h2_stoppage_settled=8.0,
)

# Score-state multipliers are scaled by 0.950, the reciprocal of the
# exposure-weighted mean multiplier, so kickoff goal means match the
# pre-match lambdas that anchor the chain.
FITTED = HazardParams(
    profile=_step_profile((0.846, 0.851, 0.894, 1.087, 1.114, 1.209)),
    h1_stoppage_intensity=0.894,
    level=0.950,
    trailing_one=1.099,
    trailing_two=1.432,
    leading=0.917,
    red_sanctioned=0.512,
    red_opponent=1.199,
    h1_stoppage=4.0,
    h2_stoppage_close=9.0,
    h2_stoppage_settled=8.0,
)


@dataclass(frozen=True)
class MatchState:
    minute: float
    home_goals: int
    away_goals: int
    home_reds: int = 0
    away_reds: int = 0


def _red_multipliers(home_reds: int, away_reds: int, params: HazardParams) -> tuple[float, float]:
    deficit = min(home_reds, 2) - min(away_reds, 2)
    if deficit == 0:
        return 1.0, 1.0
    sanctioned = params.red_sanctioned ** abs(deficit)
    opponent = params.red_opponent ** abs(deficit)
    return (sanctioned, opponent) if deficit > 0 else (opponent, sanctioned)


def _step(grid: np.ndarray, p_home: np.ndarray, p_away: np.ndarray) -> np.ndarray:
    """One minute: at most one goal per side, score-dependent rates."""
    stay = grid * (1.0 - p_home) * (1.0 - p_away)
    advanced = np.zeros_like(grid)
    advanced[1:, :] += grid[:-1, :] * p_home[:-1, :] * (1.0 - p_away[:-1, :])
    advanced[:, 1:] += grid[:, :-1] * p_away[:, :-1] * (1.0 - p_home[:, :-1])
    advanced[1:, 1:] += grid[:-1, :-1] * p_home[:-1, :-1] * p_away[:-1, :-1]
    # The top row/column absorbs: goals beyond the cap stay at the cap.
    advanced[-1, :] += grid[-1, :] * p_home[-1, :] * (1.0 - p_away[-1, :])
    advanced[:, -1] += grid[:, -1] * p_away[:, -1] * (1.0 - p_home[:, -1])
    advanced[-1, 1:] += grid[-1, :-1] * p_home[-1, :-1] * p_away[-1, :-1]
    advanced[1:, -1] += grid[:-1, -1] * p_home[:-1, -1] * p_away[:-1, -1]
    advanced[-1, -1] += grid[-1, -1] * p_home[-1, -1] * p_away[-1, -1]
    return stay + advanced


def _rate_grids(
    lam_home: float, lam_away: float, state: MatchState, params: HazardParams, *, intensity: float
) -> tuple[np.ndarray, np.ndarray]:
    side = MAX_GOALS + 1
    margins = np.arange(side)[:, None] - np.arange(side)[None, :]

    def side_mult(m: np.ndarray) -> np.ndarray:
        return np.where(
            m > 0,
            params.leading,
            np.where(m == -1, params.trailing_one, np.where(m < -1, params.trailing_two, params.level)),
        )

    home_mult = side_mult(margins)
    away_mult = side_mult(-margins)
    red_home, red_away = _red_multipliers(state.home_reds, state.away_reds, params)
    p_home = np.minimum(lam_home / 90.0 * intensity * home_mult * red_home, 0.5)
    p_away = np.minimum(lam_away / 90.0 * intensity * away_mult * red_away, 0.5)
    return p_home, p_away


def _intensity_timeline(params: HazardParams, *, h2_stoppage: float) -> list[float]:
    """Intensity per effective minute of a full match: every core minute once,
    H1 stoppage at its half's closing intensity, H2 stoppage at the minute-90
    intensity."""
    core = list(params.profile[:90])
    return (
        core[:45]
        + [params.h1_stoppage_intensity] * int(params.h1_stoppage)
        + core[45:]
        + [params.profile[90]] * int(h2_stoppage)
    )


# Normalised on the close-game schedule so pre-match lambda is preserved there;
# settled games play shorter stoppage and score accordingly less.
@lru_cache(maxsize=4)
def _normaliser(params: HazardParams) -> float:
    return sum(_intensity_timeline(params, h2_stoppage=params.h2_stoppage_close)) / 90.0


def final_score_distribution(
    lam_home: float, lam_away: float, state: MatchState, *, params: HazardParams = FITTED
) -> ScorelineDistribution:
    """Distribution over the 90-minute final score from the current state."""
    side = MAX_GOALS + 1
    grid = np.zeros((side, side))
    grid[min(state.home_goals, MAX_GOALS), min(state.away_goals, MAX_GOALS)] = 1.0

    norm = _normaliser(params)
    for intensity in _remaining_intensities(state, params):
        p_home, p_away = _rate_grids(lam_home, lam_away, state, params, intensity=intensity / norm)
        grid = _step(grid, p_home, p_away)
    return ScorelineDistribution(grid=grid / grid.sum())


def _remaining_intensities(state: MatchState, params: HazardParams) -> list[float]:
    """Intensities for the effective minutes left. Live feeds report elapsed
    clock minutes with the first half capped at 45 and the second starting at
    46, so minute <= 45 indexes into the first half and anything later into
    the second."""
    margin = abs(state.home_goals - state.away_goals)
    h2_stoppage = params.h2_stoppage_close if margin <= 1 else params.h2_stoppage_settled
    timeline = _intensity_timeline(params, h2_stoppage=h2_stoppage)
    if state.minute <= H1_MINUTES:
        start = int(state.minute)
    else:
        played_h2 = min(max(state.minute - (H1_MINUTES + 1.0), 0.0), H2_MINUTES - 1.0)
        start = int(H1_MINUTES + params.h1_stoppage + played_h2)
    return timeline[start:]


def extra_time_distribution(
    lam_home: float, lam_away: float, state: MatchState, *, params: HazardParams = FITTED
) -> ScorelineDistribution:
    """Flat-rate extra time from a level state; rates do not ramp (evidence:
    ET scoring sits at the match average, not the late-regulation peak)."""
    side = MAX_GOALS + 1
    grid = np.zeros((side, side))
    grid[min(state.home_goals, MAX_GOALS), min(state.away_goals, MAX_GOALS)] = 1.0
    p_home, p_away = _rate_grids(lam_home, lam_away, state, params, intensity=1.0 / _normaliser(params))
    for _ in range(int(ET_MINUTES)):
        grid = _step(grid, p_home, p_away)
    return ScorelineDistribution(grid=grid / grid.sum())


def live_win_probabilities(
    lam_home: float, lam_away: float, state: MatchState, *, knockout: bool, params: HazardParams = FITTED
) -> dict[str, float]:
    """Outcome probabilities from here. For knockouts the draw mass resolves
    through flat extra time and a 50/50 shootout into win probabilities."""
    regulation = final_score_distribution(lam_home, lam_away, state, params=params)
    if not knockout:
        return {"home": regulation.p_home, "draw": regulation.p_draw, "away": regulation.p_away}

    level = np.diag(regulation.grid)
    p_home, p_away = regulation.p_home, regulation.p_away
    for goals, mass in enumerate(level):
        if mass <= 0.0:
            continue
        et_state = MatchState(
            minute=0.0, home_goals=goals, away_goals=goals, home_reds=state.home_reds, away_reds=state.away_reds
        )
        et = extra_time_distribution(lam_home, lam_away, et_state, params=params)
        p_home += mass * (et.p_home + 0.5 * et.p_draw)
        p_away += mass * (et.p_away + 0.5 * et.p_draw)
    return {"home": float(p_home), "draw": 0.0, "away": float(p_away)}
