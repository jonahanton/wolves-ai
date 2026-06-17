from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.sim.distributions import reach_by_draw, shrink_draws, weighted_quantiles
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine

LEVELS = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)


def test_distribution_quantiles_decrease_across_stages() -> None:
    state = synthetic_state()
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.005)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=50)
    result = run_tournament(FMT, engine, n_sims=5_000, seed=3)
    per_draw = reach_by_draw(FMT, result, parameter_draws=engine.parameter_draws)
    sims_per_draw = result.n_sims // engine.parameter_draws

    for i in range(0, len(FMT.teams), 7):
        shrunk = shrink_draws(per_draw[i], sims_per_draw=sims_per_draw)
        previous = None
        for s in range(shrunk.shape[0]):
            weights = np.full(shrunk.shape[1], 1.0 / shrunk.shape[1])
            quantiles = np.array(weighted_quantiles(shrunk[s], weights, LEVELS))
            if previous is not None:
                assert (quantiles <= previous + 1e-9).all()
            previous = quantiles
