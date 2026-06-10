from __future__ import annotations

import numpy as np

from wolves.gate.encompassing import encompassing_test


def _world(rng: np.random.Generator, n: int, *, informative_model: bool):
    truth = rng.dirichlet([4, 3, 3], size=n)
    outcomes = np.array([rng.choice(3, p=p) for p in truth])

    def noisy(scale: float) -> np.ndarray:
        jittered = np.clip(truth + rng.normal(0, scale, truth.shape), 0.02, None)
        return jittered / jittered.sum(axis=1, keepdims=True)

    market = noisy(0.08)
    model = noisy(0.08) if informative_model else rng.dirichlet([1, 1, 1], size=n)
    return model, market, outcomes


def test_informative_model_earns_weight_and_significance() -> None:
    model, market, outcomes = _world(np.random.default_rng(5), 3000, informative_model=True)
    result = encompassing_test(model, market, outcomes)
    assert result.blend_weight > 0.2
    assert result.p_value < 0.05
    assert result.significant


def test_noise_model_is_refused_by_a_calibrated_market() -> None:
    rng = np.random.default_rng(5)
    truth = rng.dirichlet([4, 3, 3], size=3000)
    outcomes = np.array([rng.choice(3, p=p) for p in truth])
    noise = rng.dirichlet([1, 1, 1], size=3000)

    result = encompassing_test(noise, truth, outcomes)

    assert result.blend_weight < 0.05
    assert not result.significant
