from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.forecast import StrengthPerturbation
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.spread import mixture_spread_rows


class _StubForecaster:
    fmt = FMT

    def simulate(self, *, n_sims=20_000, seed=0, perturbations=()):
        overrides = {}
        for p in perturbations:
            overrides[p.team] = overrides.get(p.team, 0.0) + p.delta
        state = synthetic_state(overrides or None)
        object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.005)
        engine = PoissonMatchEngine(FMT, state, parameter_draws=200)
        return run_tournament(FMT, engine, n_sims=n_sims, seed=seed)


def test_mixture_spread_quick_look_reads_width_against_the_floor() -> None:
    worlds = {
        "base": (0.7, []),
        "england_up": (0.3, [StrengthPerturbation(team="england", delta=0.2, reason="test branch")]),
    }

    result = mixture_spread_rows(_StubForecaster(), worlds, focus_team="england", n_sims=2_000, seed=5)

    assert result.provenance == "worlds_and_parameters"
    assert result.n_worlds == 2
    england = next(r for r in result.rows if r.team == "england")
    assert set(england.world_means) == {"base", "england_up"}
    assert england.world_means["england_up"] > england.world_means["base"]
    # A real strength branch widens the mixture beyond the single-world floor.
    assert england.vs_floor > 1.0
    assert england.p10 <= england.mean <= england.p90
    assert "england band" in result.note
    floor_row = next(r for r in result.rows if r.team == "england")
    assert floor_row.floor_width_pp > 0
