from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.config import Settings
from wolves.publish_distributions import build_distributions
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_team_reach


def _world(delta_team: str | None, seed: int):
    overrides = {delta_team: 0.25} if delta_team else None
    state = synthetic_state(overrides)
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.005)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=50)
    return run_tournament(FMT, engine, n_sims=5_000, seed=seed)


def test_snapshot_distributions_block_quantiles_bound_published_means(tmp_path) -> None:
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    weights = {"base": 0.7, "branch": 0.3}
    per_world = {"base": _world(None, 1), "branch": _world("england", 1)}

    block, sidecar = build_distributions(FMT, per_world, weights, parameter_draws=50, settings=settings)

    assert block.quantile_levels == settings.distribution_quantiles
    assert block.provenance == "worlds_and_parameters"
    assert block.n_worlds == 2

    reach = {name: build_team_reach(FMT, result) for name, result in per_world.items()}
    checked = 0
    for team_id, dist in block.teams.items():
        for stage, quantiles in dist.quantiles.items():
            mixed_mean = sum(weights[name] * reach[name][team_id][stage] for name in weights)
            assert quantiles[0] <= mixed_mean + 0.01
            assert quantiles[-1] >= mixed_mean - 0.01
            assert stage not in dist.settled
            checked += 1
        for stage in dist.settled:
            assert stage not in dist.quantiles
    assert checked > 50

    for team_id, stages in sidecar.teams.items():
        for stage, shape in stages.items():
            assert stage in block.teams[team_id].quantiles
            assert len(shape.histogram) == settings.distribution_bins
            assert set(shape.world_bins) == set(weights)
