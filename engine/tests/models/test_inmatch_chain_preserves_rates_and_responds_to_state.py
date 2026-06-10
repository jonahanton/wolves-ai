from __future__ import annotations

import numpy as np
import pytest

from wolves.models.inmatch import MatchState, final_score_distribution, live_win_probabilities


def test_kickoff_distribution_preserves_prematch_goal_means() -> None:
    dist = final_score_distribution(1.5, 1.1, MatchState(minute=0, home_goals=0, away_goals=0))
    goals = np.arange(dist.grid.shape[0])
    # Trailing boosts outweigh the leading damp, so a small upward drift is inherent.
    assert (goals * dist.grid.sum(axis=1)).sum() == pytest.approx(1.5, rel=0.04)
    assert (goals * dist.grid.sum(axis=0)).sum() == pytest.approx(1.1, rel=0.04)


def test_a_lead_hardens_as_the_clock_runs() -> None:
    probs = [
        final_score_distribution(1.4, 1.2, MatchState(minute=m, home_goals=1, away_goals=0)).p_home
        for m in (50, 70, 85)
    ]
    assert probs[0] < probs[1] < probs[2]
    assert probs[2] > 0.8


def test_red_card_shifts_the_balance() -> None:
    level = MatchState(minute=60, home_goals=0, away_goals=0)
    short_handed = MatchState(minute=60, home_goals=0, away_goals=0, home_reds=1)
    assert final_score_distribution(1.3, 1.3, short_handed).p_home < final_score_distribution(1.3, 1.3, level).p_home


def test_knockout_resolution_is_even_at_the_shootout() -> None:
    result = live_win_probabilities(1.3, 1.3, MatchState(minute=89, home_goals=0, away_goals=0), knockout=True)
    assert result["draw"] == 0.0
    assert result["home"] == pytest.approx(result["away"], abs=0.005)
    assert result["home"] + result["away"] == pytest.approx(1.0)
