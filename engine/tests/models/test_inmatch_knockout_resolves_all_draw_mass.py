from __future__ import annotations

import pytest

from wolves.models.inmatch import MatchState, live_win_probabilities


@pytest.mark.parametrize(
    "state",
    [
        MatchState(minute=89, home_goals=0, away_goals=0),
        MatchState(minute=70, home_goals=2, away_goals=2, home_reds=1),
        MatchState(minute=30, home_goals=1, away_goals=0),
    ],
)
def test_knockout_probabilities_sum_to_one_with_no_draw(state) -> None:
    result = live_win_probabilities(1.4, 1.1, state, knockout=True)
    assert result["draw"] == 0.0
    assert result["home"] + result["away"] == pytest.approx(1.0)


def test_even_sides_split_the_shootout() -> None:
    result = live_win_probabilities(1.3, 1.3, MatchState(minute=89, home_goals=0, away_goals=0), knockout=True)
    assert result["home"] == pytest.approx(result["away"], abs=0.005)
