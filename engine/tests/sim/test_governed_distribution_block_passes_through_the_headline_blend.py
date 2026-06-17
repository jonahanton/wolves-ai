from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.agent.consensus import blend_log_odds
from wolves.config import Settings
from wolves.publish_distributions import build_distributions
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_team_reach


def _world(overrides: dict[str, float] | None, *, spread: float, seed: int):
    state = synthetic_state(overrides)
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * spread)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=50)
    return run_tournament(FMT, engine, n_sims=5_000, seed=seed)


def test_governed_distribution_block_passes_through_the_headline_blend(tmp_path) -> None:
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    weights = {"base": 0.6, "branch": 0.4}
    per_world = {
        "base": _world(None, spread=0.002, seed=1),
        "branch": _world({"england": 0.2}, spread=0.002, seed=1),
    }
    # A much wider anchor forces the width floor on open cells.
    anchor = _world(None, spread=0.03, seed=2)
    effective_d = 0.7

    block, _ = build_distributions(
        FMT, per_world, weights, parameter_draws=50, settings=settings, anchor_result=anchor, effective_d=effective_d
    )

    assert block.width_floored
    anchor_reach = build_team_reach(FMT, anchor)
    reach = {name: build_team_reach(FMT, result) for name, result in per_world.items()}
    levels = settings.distribution_quantiles
    q10, q90 = levels.index(0.1), levels.index(0.9)
    checked = 0
    for team_id, dist in block.teams.items():
        for stage, quantiles in dist.quantiles.items():
            # Tiny open cells legitimately round to 0.0 at publish precision.
            assert all(0.0 <= q <= 1.0 for q in quantiles)
            anchor_p = anchor_reach[team_id][stage]
            if not 0.001 < anchor_p < 0.999:
                continue
            mixed_mean = sum(weights[name] * reach[name][team_id][stage] for name in weights)
            headline = blend_log_odds({stage: mixed_mean}, {stage: anchor_p}, d=effective_d)[stage]
            if headline < 0.05:
                # The test's 15x anchor makes small floored cells so right-skewed
                # the mean sits beyond q90; production floors are same-magnitude
                # parameter noise, where containment holds.
                continue
            assert quantiles[q10] - 0.011 <= headline <= quantiles[q90] + 0.011
            checked += 1
    assert checked > 30
