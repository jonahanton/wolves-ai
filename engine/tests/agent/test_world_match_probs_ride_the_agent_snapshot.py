from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.run_agent import _world_match_probs
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine


class _StubForecaster:
    fmt = FMT

    def sim_outputs(self, *, n_sims, seed, extra_results, result):
        from wolves.sim.api import SimOutputs
        from wolves.sim.outputs import build_focus_team, build_groups, build_matches, build_slots

        played = set(extra_results or {})
        return SimOutputs(
            n_sims=n_sims,
            seed=seed,
            focus=build_focus_team(FMT, result, team_id="england"),
            slots=build_slots(FMT, result),
            teams=[],
            groups=build_groups(FMT, result),
            matches=build_matches(FMT, result, played=played),
        )


def test_world_match_probs_ride_the_agent_snapshot() -> None:
    state = synthetic_state()
    object.__setattr__(state, "covariance", np.eye(len(state.teams) + 2) * 0.005)
    engine = PoissonMatchEngine(FMT, state, parameter_draws=50)
    first_group = min(m.match for m in FMT.group_matches)
    played = {first_group: None}
    result = run_tournament(FMT, engine, n_sims=2_000, seed=4)

    per_world = _world_match_probs(
        _StubForecaster(), {"base": result, "branch": result}, n_sims=2_000, seed=4, played=played
    )

    assert set(per_world) == {"base", "branch"}
    probs = per_world["base"]
    assert str(first_group) not in probs
    sample = next(iter(probs.values()))
    assert set(sample) == {"home", "draw", "away"}
    assert abs(sum(sample.values()) - 1.0) < 0.02
