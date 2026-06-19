from __future__ import annotations

import numpy as np
import pytest

from wolves.models.inmatch import FITTED, INCUMBENT, MatchState, final_score_distribution, live_win_probabilities


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


def test_sixtieth_minute_red_card_swings_a_level_knockout_about_23pp() -> None:
    """A 60' red card to the home side in a level knockout hands the opponent
    roughly a 73% win, a swing the calibrated opponent multiplier must preserve."""
    level = MatchState(minute=60, home_goals=0, away_goals=0)
    red_home = MatchState(minute=60, home_goals=0, away_goals=0, home_reds=1)
    before = live_win_probabilities(1.3, 1.3, level, knockout=True)["away"]
    after = live_win_probabilities(1.3, 1.3, red_home, knockout=True)["away"]
    assert before == pytest.approx(0.5, abs=1e-6)
    assert after == pytest.approx(0.726, abs=0.01)
