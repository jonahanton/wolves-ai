"""In-match model: final-score distribution conditional on minute, score and
red cards. A deterministic Markov chain over scoreline states in one-minute
steps (no Monte Carlo), with a rising intensity profile, the post-2022 FIFA
stoppage regime, score-state multipliers and a flat extra-time rate."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from wolves.models.contracts import MAX_GOALS, ScorelineDistribution

H1_MINUTES = 45.0
H2_MINUTES = 45.0
H1_STOPPAGE = 4.0
H2_STOPPAGE_CLOSE = 9.0
H2_STOPPAGE_SETTLED = 8.0
ET_MINUTES = 33.0

# Piecewise-linear scoring intensity by minute, normalised to mean 1 over 90.
_PROFILE_KNOTS = ((0.0, 0.85), (45.0, 1.05), (45.001, 1.05), (90.0, 1.45))
TRAILING_ONE = 1.10
TRAILING_TWO = 1.20
LEADING = 0.90
RED_SANCTIONED = 0.60
RED_OPPONENT = 1.50


@dataclass(frozen=True)
class MatchState:
    minute: float
    home_goals: int
    away_goals: int
    home_reds: int = 0
    away_reds: int = 0


def _profile(minute: float) -> float:
    knots = _PROFILE_KNOTS
    if minute >= knots[-1][0]:
        return knots[-1][1]
    for (m0, v0), (m1, v1) in pairwise(knots):
        if m0 <= minute <= m1:
            return v0 + (v1 - v0) * (minute - m0) / (m1 - m0)
    return knots[0][1]


def _red_multipliers(home_reds: int, away_reds: int) -> tuple[float, float]:
    deficit = min(home_reds, 2) - min(away_reds, 2)
    if deficit == 0:
        return 1.0, 1.0
    sanctioned = RED_SANCTIONED ** abs(deficit)
    opponent = RED_OPPONENT ** abs(deficit)
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
    advanced[-1, -1] += grid[-1, -1] * p_home[-1, -1] * p_away[-1, -1]
    return stay + advanced


def _rate_grids(
    lam_home: float, lam_away: float, state: MatchState, *, intensity: float
) -> tuple[np.ndarray, np.ndarray]:
    side = MAX_GOALS + 1
    margins = np.arange(side)[:, None] - np.arange(side)[None, :]
    home_mult = np.where(
        margins > 0, LEADING, np.where(margins == -1, TRAILING_ONE, np.where(margins < -1, TRAILING_TWO, 1.0))
    )
    away_mult = np.where(
        margins < 0, LEADING, np.where(margins == 1, TRAILING_ONE, np.where(margins > 1, TRAILING_TWO, 1.0))
    )
    red_home, red_away = _red_multipliers(state.home_reds, state.away_reds)
    p_home = np.minimum(lam_home / 90.0 * intensity * home_mult * red_home, 0.5)
    p_away = np.minimum(lam_away / 90.0 * intensity * away_mult * red_away, 0.5)
    return p_home, p_away


# The profile must integrate to one over a full effective match, so the
# pre-match lambda is preserved when summed across all minutes.
_FULL_MATCH = [float(m) for m in np.arange(0.0, H1_MINUTES + H1_STOPPAGE)] + [
    float(m) for m in np.arange(H1_MINUTES, H1_MINUTES + H2_MINUTES + H2_STOPPAGE_CLOSE)
]
_NORMALISER = sum(_profile(min(m, 90.0)) for m in _FULL_MATCH) / 90.0


def final_score_distribution(lam_home: float, lam_away: float, state: MatchState) -> ScorelineDistribution:
    """Distribution over the 90-minute final score from the current state."""
    side = MAX_GOALS + 1
    grid = np.zeros((side, side))
    grid[min(state.home_goals, MAX_GOALS), min(state.away_goals, MAX_GOALS)] = 1.0

    for minute in _remaining_minutes(state):
        p_home, p_away = _rate_grids(lam_home, lam_away, state, intensity=_profile(min(minute, 90.0)) / _NORMALISER)
        grid = _step(grid, p_home, p_away)
    return ScorelineDistribution(grid=grid / grid.sum())


def _remaining_minutes(state: MatchState) -> list[float]:
    """Effective minutes left under the post-2022 stoppage regime."""
    margin = abs(state.home_goals - state.away_goals)
    h2_stoppage = H2_STOPPAGE_CLOSE if margin <= 1 else H2_STOPPAGE_SETTLED
    minutes: list[float] = []
    if state.minute < H1_MINUTES + H1_STOPPAGE:
        first_half_end = H1_MINUTES + H1_STOPPAGE
        minutes.extend(np.arange(state.minute, first_half_end))
        minutes.extend(np.arange(H1_MINUTES, H1_MINUTES + H2_MINUTES + h2_stoppage))
    else:
        # Mid second half: clock minutes past 45 map onto the H2 profile directly.
        second_half_end = H1_MINUTES + H2_MINUTES + h2_stoppage
        minutes.extend(np.arange(state.minute, second_half_end))
    return [float(m) for m in minutes]


def extra_time_distribution(lam_home: float, lam_away: float, state: MatchState) -> ScorelineDistribution:
    """Flat-rate extra time from a level state; rates do not ramp (evidence:
    ET scoring sits at the match average, not the late-regulation peak)."""
    side = MAX_GOALS + 1
    grid = np.zeros((side, side))
    grid[min(state.home_goals, MAX_GOALS), min(state.away_goals, MAX_GOALS)] = 1.0
    p_home, p_away = _rate_grids(lam_home, lam_away, state, intensity=1.0 / _NORMALISER)
    for _ in range(int(ET_MINUTES)):
        grid = _step(grid, p_home, p_away)
    return ScorelineDistribution(grid=grid / grid.sum())


def live_win_probabilities(lam_home: float, lam_away: float, state: MatchState, *, knockout: bool) -> dict[str, float]:
    """Outcome probabilities from here. For knockouts the draw mass resolves
    through flat extra time and a 50/50 shootout into win probabilities."""
    regulation = final_score_distribution(lam_home, lam_away, state)
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
        et = extra_time_distribution(lam_home, lam_away, et_state)
        p_home += mass * (et.p_home + 0.5 * et.p_draw)
        p_away += mass * (et.p_away + 0.5 * et.p_draw)
    return {"home": float(p_home), "draw": 0.0, "away": float(p_away)}
