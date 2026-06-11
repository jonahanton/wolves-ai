from __future__ import annotations

from datetime import date

import pytest

from wolves.config import Settings
from wolves.run_policy import agent_ceiling, day_policy
from wolves.sim.format import load_format

SETTINGS = Settings()
FMT = load_format(SETTINGS.data_dir)


def test_rest_day_gets_the_floor() -> None:
    assert agent_ceiling(SETTINGS, FMT, on=date(2026, 7, 17)) == SETTINGS.agent_ceiling_rest_day_usd


@pytest.mark.parametrize(
    ("quieter", "busier"),
    [
        (date(2026, 6, 13), date(2026, 6, 28)),
        (date(2026, 6, 29), date(2026, 7, 7)),
    ],
)
def test_bigger_calendar_days_get_bigger_ceilings(quieter: date, busier: date) -> None:
    assert agent_ceiling(SETTINGS, FMT, on=quieter) < agent_ceiling(SETTINGS, FMT, on=busier)


def test_focus_team_group_days_carry_the_bonus() -> None:
    with_focus = day_policy(SETTINGS, FMT, on=date(2026, 6, 17))
    without = day_policy(SETTINGS, FMT, on=date(2026, 6, 16))

    assert with_focus.focus_involved
    assert not without.focus_involved
    assert with_focus.ceiling_usd > without.ceiling_usd


def test_ceiling_clamps_to_the_policy_max() -> None:
    greedy = SETTINGS.model_copy(update={"agent_ceiling_knockout_today_usd": 50.0})

    assert agent_ceiling(greedy, FMT, on=date(2026, 7, 19)) == greedy.agent_ceiling_policy_max_usd
