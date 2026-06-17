from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.sim.distributions import STAGES, reach_by_draw
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_team_reach


def test_reach_by_draw_matches_engine_draw_assignment() -> None:
    state = synthetic_state()
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.005)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=50)
    result = run_tournament(FMT, engine, n_sims=5_000, seed=11)

    per_draw = reach_by_draw(FMT, result, parameter_draws=engine.parameter_draws)
    aggregate = build_team_reach(FMT, result)

    means = per_draw.mean(axis=2)
    for i, team in enumerate(FMT.teams):
        for s, stage in enumerate(STAGES):
            assert abs(means[i, s] - aggregate[team.id][stage]) < 5e-5
