from __future__ import annotations

import numpy as np

TOTAL_GOALS = 2.6


def expected_score(elo_a: np.ndarray, elo_b: np.ndarray) -> np.ndarray:
    """Classic Elo win expectancy for side A."""
    return 1.0 / (1.0 + 10.0 ** (-(elo_a - elo_b) / 400.0))


def goal_means(elo_a: np.ndarray, elo_b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split a fixed goal budget by Elo expectancy."""
    w = expected_score(elo_a, elo_b)
    return TOTAL_GOALS * w, TOTAL_GOALS * (1.0 - w)


def simulate_goals(
    rng: np.random.Generator, elo_a: np.ndarray | float, elo_b: np.ndarray | float, n: int
) -> tuple[np.ndarray, np.ndarray]:
    lam_a, lam_b = goal_means(np.asarray(elo_a), np.asarray(elo_b))
    return rng.poisson(np.broadcast_to(lam_a, (n,))), rng.poisson(np.broadcast_to(lam_b, (n,)))
