"""Pins the sign of the score-state multipliers: a confounded refit (no team
strength control) inverts them, making leaders score faster than trailers."""

from __future__ import annotations

import numpy as np
import pytest

from wolves.models.inmatch import FITTED, INCUMBENT, MatchState, final_score_distribution


def expected_additional_home_goals(state: MatchState, params) -> float:
    dist = final_score_distribution(1.2, 1.2, state, params=params)
    goals = np.arange(dist.grid.shape[0])
    return float((goals * dist.grid.sum(axis=1)).sum()) - state.home_goals


@pytest.mark.parametrize("params", [INCUMBENT, FITTED], ids=["incumbent", "fitted"])
@pytest.mark.parametrize("deficit", [1, 2])
def test_trailing_side_outscores_leading_side_from_here(params, deficit) -> None:
    trailing = MatchState(minute=60, home_goals=0, away_goals=deficit)
    leading = MatchState(minute=60, home_goals=deficit, away_goals=0)
    assert expected_additional_home_goals(trailing, params) > expected_additional_home_goals(leading, params)


def test_two_goal_deficit_presses_harder_than_one() -> None:
    assert FITTED.trailing_two > FITTED.trailing_one > 1.0 > FITTED.leading
