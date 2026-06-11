from __future__ import annotations

from wolves.models.inmatch import MatchState, final_score_distribution, live_win_probabilities


def _et_state(minute: float, home_goals: int, away_goals: int) -> MatchState:
    return MatchState(minute=minute, home_goals=home_goals, away_goals=away_goals, period="extra_time")


def test_shootout_state_is_a_coin_flip() -> None:
    state = MatchState(minute=120.0, home_goals=1, away_goals=1, period="shootout")

    assert live_win_probabilities(1.4, 1.2, state, knockout=True) == {"home": 0.5, "draw": 0.0, "away": 0.5}


def test_extra_time_level_state_resolves_towards_the_shootout_coin_flip() -> None:
    early = live_win_probabilities(1.8, 0.9, _et_state(91.0, 1, 1), knockout=True)
    late = live_win_probabilities(1.8, 0.9, _et_state(119.0, 1, 1), knockout=True)

    assert early["draw"] == 0.0 and late["draw"] == 0.0
    assert abs(late["home"] - 0.5) < abs(early["home"] - 0.5)


def test_extra_time_lead_hardens_as_minutes_run_out() -> None:
    early = live_win_probabilities(1.4, 1.2, _et_state(95.0, 2, 1), knockout=True)
    late = live_win_probabilities(1.4, 1.2, _et_state(119.0, 2, 1), knockout=True)

    assert late["home"] > early["home"] > 0.5
    assert late["home"] > 0.9


def test_extra_time_distribution_starts_from_the_current_score_not_regulation() -> None:
    dist = final_score_distribution(1.4, 1.2, _et_state(119.0, 2, 1))

    assert dist.grid[2, 1] > 0.8
    assert dist.grid[:2, :].sum() == 0.0
