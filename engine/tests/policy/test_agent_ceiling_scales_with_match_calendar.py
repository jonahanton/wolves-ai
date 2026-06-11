from __future__ import annotations

from datetime import date

import pytest

from wolves.config import Settings
from wolves.run_policy import day_policy
from wolves.sim.format import load_format

SETTINGS = Settings()
FMT = load_format(SETTINGS.data_dir)


@pytest.mark.parametrize(
    ("on", "phase"),
    [
        (date(2026, 6, 12), "opening"),
        (date(2026, 6, 23), "big_group"),
        (date(2026, 6, 25), "big_group"),
        (date(2026, 6, 29), "r32_r16"),
        (date(2026, 7, 10), "qf_final"),
        (date(2026, 7, 19), "qf_final"),
        (date(2026, 7, 17), "rest"),
    ],
)
def test_days_classify_into_their_phase(on: date, phase: str) -> None:
    assert day_policy(SETTINGS, FMT, on=on).phase == phase


def test_focus_team_marks_a_group_day_big_even_without_elo_top_sides() -> None:
    no_elo_bigs = SETTINGS.model_copy(update={"agent_big_team_count": 0})
    england_day = day_policy(no_elo_bigs, FMT, on=date(2026, 6, 23))

    assert england_day.phase == "big_group"
    assert england_day.big_teams == ("england",)


def test_phase_ceilings_follow_the_settings_table() -> None:
    assert day_policy(SETTINGS, FMT, on=date(2026, 6, 12)).ceiling_usd == SETTINGS.agent_ceiling_opening_usd
    assert day_policy(SETTINGS, FMT, on=date(2026, 7, 19)).ceiling_usd == SETTINGS.agent_ceiling_qf_final_usd
    assert day_policy(SETTINGS, FMT, on=date(2026, 7, 17)).ceiling_usd == SETTINGS.agent_ceiling_rest_usd


def test_ceiling_clamps_to_the_absolute_max() -> None:
    greedy = SETTINGS.model_copy(update={"agent_ceiling_qf_final_usd": 50.0})

    assert day_policy(greedy, FMT, on=date(2026, 7, 19)).ceiling_usd == greedy.agent_run_ceiling_max_usd
