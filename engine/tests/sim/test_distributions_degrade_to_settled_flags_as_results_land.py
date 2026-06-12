from __future__ import annotations

import numpy as np

from wolves.sim.distributions import cell_distribution

LEVELS = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
WEIGHTS = {"base": 0.8, "branch": 0.2}


def _cell(value: float) -> dict[str, np.ndarray]:
    return {name: np.full(200, value) for name in WEIGHTS}


def test_distributions_degrade_to_settled_flags_as_results_land() -> None:
    eliminated = cell_distribution(_cell(0.0), WEIGHTS, sims_per_draw=250, quantile_levels=LEVELS, n_bins=20)
    assert eliminated.settled == 0
    assert eliminated.quantiles is None
    assert eliminated.histogram is None
    assert eliminated.components is None

    achieved = cell_distribution(_cell(1.0), WEIGHTS, sims_per_draw=250, quantile_levels=LEVELS, n_bins=20)
    assert achieved.settled == 1
    assert achieved.quantiles is None

    near_certain = cell_distribution(_cell(0.001), WEIGHTS, sims_per_draw=250, quantile_levels=LEVELS, n_bins=20)
    assert near_certain.settled is None
    assert near_certain.quantiles is not None
    assert len(set(near_certain.quantiles)) == 1
