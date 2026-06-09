from __future__ import annotations

import math

import numpy as np

from wolves.sim.match import BASE_GOALS, simulate_goals


def _poisson_draw_prob(lam: float) -> float:
    pmf = [math.exp(-lam) * lam**k / math.factorial(k) for k in range(30)]
    return sum(p * p for p in pmf)


def test_equal_sides_draw_more_often_than_independent_poisson():
    n = 400_000
    lam = np.full(n, BASE_GOALS)
    home, away = simulate_goals(np.random.default_rng(0), lam, lam)
    empirical = float((home == away).mean())
    baseline = _poisson_draw_prob(BASE_GOALS)
    assert empirical > baseline + 0.005
