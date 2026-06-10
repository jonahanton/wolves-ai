from __future__ import annotations

import numpy as np
import pytest

from wolves.models.inmatch import FITTED, INCUMBENT, MatchState, extra_time_distribution, final_score_distribution

STATES = (
    MatchState(minute=0, home_goals=0, away_goals=0),
    MatchState(minute=44.5, home_goals=2, away_goals=1),
    MatchState(minute=60, home_goals=0, away_goals=3, home_reds=1, away_reds=2),
    MatchState(minute=89.9, home_goals=12, away_goals=0),
)


@pytest.mark.parametrize("params", [INCUMBENT, FITTED], ids=["incumbent", "fitted"])
@pytest.mark.parametrize("state", STATES)
def test_regulation_grid_is_a_distribution(params, state) -> None:
    dist = final_score_distribution(1.8, 0.9, state, params=params)
    assert np.isfinite(dist.grid).all()
    assert (dist.grid >= 0).all()
    assert dist.grid.sum() == pytest.approx(1.0)


@pytest.mark.parametrize("params", [INCUMBENT, FITTED], ids=["incumbent", "fitted"])
def test_extra_time_grid_is_a_distribution(params) -> None:
    dist = extra_time_distribution(1.2, 1.2, MatchState(minute=0, home_goals=2, away_goals=2), params=params)
    assert np.isfinite(dist.grid).all()
    assert dist.grid.sum() == pytest.approx(1.0)
