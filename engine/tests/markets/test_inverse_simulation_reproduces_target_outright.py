from __future__ import annotations

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.markets.inverse import strengths_matching_outright, title_probabilities


def test_offsets_move_the_simulated_outright_to_the_market() -> None:
    state = synthetic_state()
    base = title_probabilities(FMT, state, seed=11, n_sims=5000)
    target = dict(base)
    target["england"] *= 1.8
    total = sum(target.values())
    target = {k: v / total for k, v in target.items()}

    adjusted, offsets = strengths_matching_outright(FMT, state, target, seed=11, n_sims=5000)
    achieved = title_probabilities(FMT, adjusted, seed=99, n_sims=20000)

    assert offsets["england"] > 0.0
    assert abs(achieved["england"] - target["england"]) < 0.35 * target["england"]
