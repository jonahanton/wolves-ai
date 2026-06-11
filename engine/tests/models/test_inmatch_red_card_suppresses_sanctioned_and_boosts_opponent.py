from __future__ import annotations

import numpy as np
import pytest

from wolves.models.inmatch import FITTED, INCUMBENT, MatchState, final_score_distribution


def expected_goals(state: MatchState, params) -> tuple[float, float]:
    dist = final_score_distribution(1.3, 1.3, state, params=params)
    goals = np.arange(dist.grid.shape[0])
    home = float((goals * dist.grid.sum(axis=1)).sum())
    away = float((goals * dist.grid.sum(axis=0)).sum())
    return home, away


@pytest.mark.parametrize("params", [INCUMBENT, FITTED], ids=["incumbent", "fitted"])
def test_red_card_cuts_sanctioned_side_and_lifts_opponent(params) -> None:
    level = MatchState(minute=60, home_goals=1, away_goals=1)
    short_handed = MatchState(minute=60, home_goals=1, away_goals=1, home_reds=1)
    home_full, away_full = expected_goals(level, params)
    home_short, away_short = expected_goals(short_handed, params)
    assert home_short < home_full
    assert away_short > away_full


def test_fitted_red_multipliers_keep_their_signs() -> None:
    assert FITTED.red_sanctioned < 1.0 < FITTED.red_opponent
