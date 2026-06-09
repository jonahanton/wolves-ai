from __future__ import annotations

import numpy as np

from wolves.sim.elo import expected_score

STAGE_GAP_MULT = {"group": 0.9, "knockout": 1.1}

BASE_GOALS = 1.30
MARGIN_SCALE = 4.0
MARGIN_CURVE = 620.0
TOTAL_LIFT = 1.5
MIN_GOAL_MEAN = 0.08

# Shared tempo shock correlates the two scorelines (inflating draws); the
# per-side shock over-disperses each marginal beyond Poisson.
SHARED_SHAPE = 12.0
SIDE_SHAPE = 10.0

PENS_SHARE = 0.40
SHOOTOUT_SKEW = 0.45
SHOOTOUT_EDGE_CAP = 0.60


def goal_means(diff: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Map an effective rating diff to per-side expected goals via a saturating margin curve."""
    swing = np.tanh(diff / MARGIN_CURVE)
    mu_diff = MARGIN_SCALE * swing
    mu_total = 2.0 * BASE_GOALS + TOTAL_LIFT * np.abs(swing)
    lam_home = np.maximum((mu_total + mu_diff) / 2.0, MIN_GOAL_MEAN)
    lam_away = np.maximum((mu_total - mu_diff) / 2.0, MIN_GOAL_MEAN)
    return lam_home, lam_away


def simulate_goals(
    rng: np.random.Generator, lam_home: np.ndarray, lam_away: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Draw correlated over-dispersed scorelines from per-side goal means."""
    n = lam_home.shape[0]
    shared = rng.gamma(SHARED_SHAPE, 1.0 / SHARED_SHAPE, n)
    home = rng.poisson(lam_home * shared * rng.gamma(SIDE_SHAPE, 1.0 / SIDE_SHAPE, n))
    away = rng.poisson(lam_away * shared * rng.gamma(SIDE_SHAPE, 1.0 / SIDE_SHAPE, n))
    return home, away


def knockout_home_wins(
    rng: np.random.Generator, diff: np.ndarray, home_goals: np.ndarray, away_goals: np.ndarray
) -> np.ndarray:
    """Resolve a knockout tie: 90-minute result, else extra time, else a capped shootout."""
    w_home = expected_score(diff)
    n = home_goals.shape[0]
    to_pens = rng.random(n) < PENS_SHARE
    shootout_p = np.clip(0.5 + SHOOTOUT_SKEW * (w_home - 0.5), 1.0 - SHOOTOUT_EDGE_CAP, SHOOTOUT_EDGE_CAP)
    level_winner_p = np.where(to_pens, shootout_p, w_home)
    return np.where(home_goals == away_goals, rng.random(n) < level_winner_p, home_goals > away_goals)
