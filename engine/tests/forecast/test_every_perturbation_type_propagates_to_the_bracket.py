from __future__ import annotations

import numpy as np
import pytest

from wolves.models.contracts import ScorelineDistribution


def test_reweighted_grid_hits_targets_and_keeps_shape() -> None:
    base = ScorelineDistribution(grid=np.full((11, 11), 1.0 / 121))
    skewed = base.reweighted(p_home=0.7, p_draw=0.2, p_away=0.1)

    assert skewed.p_home == pytest.approx(0.7)
    assert skewed.p_draw == pytest.approx(0.2)
    assert skewed.p_away == pytest.approx(0.1)
    # Within the home-win region relative scoreline shape is unchanged.
    assert skewed.grid[1, 0] == pytest.approx(skewed.grid[2, 0])


def test_single_scoreline_is_a_point_mass() -> None:
    dist = ScorelineDistribution.single(2, 1)
    assert dist.grid[2, 1] == 1.0
    assert dist.grid.sum() == 1.0
