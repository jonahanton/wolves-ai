from __future__ import annotations

import numpy as np

from wolves.models.poisson import poisson_grid, poisson_wdl_draws


def test_per_draw_mean_differs_from_the_point_estimate_by_a_bounded_jensen_gap() -> None:
    """The curve is a spread over parameter draws, so its mean sits a little off
    the single-point estimate at the mean rate. That Jensen gap is the reason a
    curve exists, not a bug, and it stays small."""
    rng = np.random.default_rng(0)
    lam_home = np.exp(rng.normal(np.log(1.6), 0.25, size=4000))
    lam_away = np.exp(rng.normal(np.log(1.1), 0.25, size=4000))

    p_home, p_draw, p_away = poisson_wdl_draws(lam_home, lam_away)
    point = poisson_grid(float(lam_home.mean()), float(lam_away.mean()))

    gap = abs(float(p_home.mean()) - point.p_home)
    assert gap > 1e-3
    assert gap < 0.03
    assert abs(float(p_home.mean()) + float(p_draw.mean()) + float(p_away.mean()) - 1.0) < 1e-9
