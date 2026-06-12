from __future__ import annotations

import numpy as np

from wolves.sim.distributions import apply_blend


def test_governed_band_contains_governed_headline() -> None:
    rng = np.random.default_rng(5)
    samples = np.clip(rng.normal(0.115, 0.02, 4_000), 0.01, 0.5)
    governed = apply_blend(samples, anchor=0.085, d=0.7)

    headline = apply_blend(np.array([samples.mean()]), anchor=0.085, d=0.7)[0]
    q10, q90 = np.quantile(governed, (0.1, 0.9))
    assert q10 <= headline <= q90

    raw_width = np.quantile(samples, 0.9) - np.quantile(samples, 0.1)
    assert (q90 - q10) < raw_width
