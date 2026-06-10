from __future__ import annotations

import numpy as np

from wolves.markets.blend import blend_probabilities, fit_model_weight


def test_fitted_weight_recovers_the_generating_mixture() -> None:
    rng = np.random.default_rng(3)
    true_weight = 0.3
    samples = []
    for _ in range(4000):
        model = rng.dirichlet([2, 2, 2])
        market = rng.dirichlet([2, 2, 2])
        truth = true_weight * model + (1 - true_weight) * market
        outcome = int(rng.choice(3, p=truth))
        samples.append((model, market, outcome))

    weight, loss = fit_model_weight(samples)

    assert abs(weight - true_weight) < 0.1
    assert loss < -np.mean([np.log(s[1][s[2]]) for s in samples])


def test_blend_renormalises_over_the_outcome_union() -> None:
    mixed = blend_probabilities({"a": 0.6, "b": 0.4}, {"a": 0.5, "c": 0.5}, model_weight=0.5)
    assert sum(mixed.values()) == 1.0
    assert set(mixed) == {"a", "b", "c"}
