"""our_call must equal the published champion probability so chart 1 and chart 2
never disagree; component_mean tracks the weighted mixture mean within Jensen drift."""

from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.config import Settings
from wolves.publish_distributions import build_distributions
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_team_reach


def _world(overrides: dict[str, float] | None, *, seed: int):
    state = synthetic_state(overrides)
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.002)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=50)
    return run_tournament(FMT, engine, n_sims=5_000, seed=seed)


def test_our_call_echoes_published_and_component_mean_tracks_the_mixture(tmp_path) -> None:
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    weights = {"base": 0.6, "branch": 0.4}
    per_world = {"base": _world(None, seed=1), "branch": _world({"england": 0.2}, seed=1)}
    reach = {name: build_team_reach(FMT, result) for name, result in per_world.items()}
    mixed = {
        team_id: sum(weights[name] * reach[name][team_id]["champion"] for name in weights) for team_id in reach["base"]
    }
    champion_prob = {team_id: round(p, 6) for team_id, p in mixed.items()}

    _, sidecar = build_distributions(
        FMT, per_world, weights, parameter_draws=50, settings=settings, champion_prob=champion_prob
    )

    checked = 0
    for team_id, stages in sidecar.teams.items():
        cell = stages.get("champion")
        if cell is None:
            continue
        assert cell.our_call == champion_prob[team_id]
        if 0.01 < champion_prob[team_id] < 0.99:
            assert abs(cell.component_mean - mixed[team_id]) <= 0.005
            checked += 1
    assert checked > 0
