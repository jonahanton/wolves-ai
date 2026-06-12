from __future__ import annotations

import numpy as np

from wolves.sim.distributions import floor_width


def test_width_floor_only_ever_widens() -> None:
    rng = np.random.default_rng(9)
    narrow = np.clip(rng.normal(0.11, 0.005, 2_000), 0.001, 0.999)
    wide_floor = np.clip(rng.normal(0.11, 0.02, 2_000), 0.001, 0.999)

    widened = floor_width(narrow, wide_floor)
    width = np.quantile(widened, 0.9) - np.quantile(widened, 0.1)
    floor = np.quantile(wide_floor, 0.9) - np.quantile(wide_floor, 0.1)
    assert width >= floor - 1e-6
    assert abs(widened.mean() - narrow.mean()) < 0.001

    narrow_floor = np.clip(rng.normal(0.11, 0.001, 2_000), 0.001, 0.999)
    untouched = floor_width(narrow, narrow_floor)
    assert untouched is narrow
