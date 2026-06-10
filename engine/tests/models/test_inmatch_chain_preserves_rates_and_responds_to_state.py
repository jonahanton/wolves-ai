from __future__ import annotations

import numpy as np
import pytest

from wolves.models.inmatch import FITTED, INCUMBENT, MatchState, final_score_distribution


@pytest.mark.parametrize("params", [INCUMBENT, FITTED], ids=["incumbent", "fitted"])
def test_kickoff_distribution_preserves_prematch_goal_means(params) -> None:
    dist = final_score_distribution(1.5, 1.1, MatchState(minute=0, home_goals=0, away_goals=0), params=params)
    goals = np.arange(dist.grid.shape[0])
    # The score-state mix drifts means slightly; calibration keeps it inside 4%.
    assert (goals * dist.grid.sum(axis=1)).sum() == pytest.approx(1.5, rel=0.04)
    assert (goals * dist.grid.sum(axis=0)).sum() == pytest.approx(1.1, rel=0.04)


def test_a_lead_hardens_as_the_clock_runs() -> None:
    probs = [
        final_score_distribution(1.4, 1.2, MatchState(minute=m, home_goals=1, away_goals=0)).p_home
        for m in (50, 70, 85)
    ]
    assert probs[0] < probs[1] < probs[2]
    assert probs[2] > 0.8
