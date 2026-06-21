"""Mixed slot candidates are per-side occupancy marginals, mixed by the same
weights as reach, so a team's summed occupancy equals its mixed reach. Top-N
truncation only ever drops tail mass, so the identity holds exactly for any team
still listed on every side it occupies; the final, where each team has at most
two sides, pins this without the third-place scatter of earlier rounds."""

from __future__ import annotations

import numpy as np
import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.agent.forecast_artifact import PublishedWorld, mixed_outputs
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_team_reach


def _world(overrides: dict[str, float] | None, *, seed: int):
    state = synthetic_state(overrides)
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.002)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=40)
    return run_tournament(FMT, engine, n_sims=4_000, seed=seed)


def _mixed_outputs(tmp_path, weights, *, seed):
    per_world_results = {"base": _world(None, seed=seed), "branch": _world({"england": 0.4}, seed=seed)}
    worlds = [PublishedWorld(name=name, weight=weights[name]) for name in weights]
    forecaster = Forecaster(Settings(_env_file=None, runs_root=tmp_path, storage_mode="local"))
    object.__setattr__(forecaster, "fmt", FMT)
    outputs = mixed_outputs(forecaster, worlds, n_sims=4_000, seed=seed, per_world_results=per_world_results)
    per_world_reach = {name: build_team_reach(FMT, result) for name, result in per_world_results.items()}
    reach = {
        team.id: {
            stage: sum(w * per_world_reach[name][team.id][stage] for name, w in weights.items())
            for stage in ("r32", "r16", "qf", "sf", "final")
        }
        for team in FMT.teams
    }
    return outputs, reach


def test_final_side_marginals_sum_to_mixed_final_reach(tmp_path) -> None:
    weights = {"base": 0.55, "branch": 0.45}
    outputs, reach = _mixed_outputs(tmp_path, weights, seed=7)
    final = next(s for s in outputs.slots if s.stage == "final")
    home = {c.team_id: c.prob for c in final.home.candidates}
    away = {c.team_id: c.prob for c in final.away.candidates}

    for team_id in home.keys() & away.keys():
        assert home[team_id] + away[team_id] == pytest.approx(reach[team_id]["final"], abs=2e-3)


def test_listed_candidate_probability_never_exceeds_mixed_reach(tmp_path) -> None:
    weights = {"base": 0.6, "branch": 0.4}
    outputs, reach = _mixed_outputs(tmp_path, weights, seed=11)
    for slot in outputs.slots:
        if slot.stage == "third_place":
            continue
        for side in (slot.home, slot.away):
            for c in side.candidates:
                assert c.prob <= reach[c.team_id][slot.stage] + 2e-3
