from __future__ import annotations

import numpy as np

from wolves.sim.distributions import _pooled, shrink_draws, weighted_quantiles

WEIGHTS = {"main": 0.70, "low": 0.15, "high": 0.15}
MEANS = {"main": 0.11, "low": 0.08, "high": 0.16}
EPISTEMIC_SD = 0.015
DRAWS = 200
SIMS_PER_DRAW = 250
TRUE_Q10, TRUE_Q90 = 0.0813, 0.1539


def _observe(seed: int) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    rng = np.random.default_rng(seed)
    raw: dict[str, np.ndarray] = {}
    shrunk: dict[str, np.ndarray] = {}
    for name in WEIGHTS:
        true_p = rng.normal(MEANS[name], EPISTEMIC_SD, DRAWS)
        observed = rng.binomial(SIMS_PER_DRAW, np.clip(true_p, 0.0, 1.0), DRAWS) / SIMS_PER_DRAW
        raw[name] = observed
        shrunk[name] = shrink_draws(observed, sims_per_draw=SIMS_PER_DRAW)
    return raw, shrunk


def test_shrinkage_recovers_analytic_mixture_quantiles() -> None:
    raw, shrunk = _observe(seed=7)

    samples, weights = _pooled(shrunk, WEIGHTS)
    q10, q90 = weighted_quantiles(samples, weights, (0.1, 0.9))
    assert abs(q10 - TRUE_Q10) < 0.0035
    assert abs(q90 - TRUE_Q90) < 0.0035

    raw_samples, raw_weights = _pooled(raw, WEIGHTS)
    raw_q10, raw_q90 = weighted_quantiles(raw_samples, raw_weights, (0.1, 0.9))
    assert raw_q90 - raw_q10 > q90 - q10
