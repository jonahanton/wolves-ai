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
        (date(2026, 6, 18), "opening"),
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


@pytest.mark.parametrize(
    ("morning_after", "phase"),
    [
        (date(2026, 7, 8), "r32_r16"),
        (date(2026, 7, 13), "qf_final"),
        (date(2026, 7, 16), "qf_final"),
        (date(2026, 7, 20), "qf_final"),
    ],
)
def test_morning_runs_digest_the_previous_evening_at_its_rate(morning_after: date, phase: str) -> None:
    assert day_policy(SETTINGS, FMT, on=morning_after).phase == phase


def test_focus_team_marks_a_group_day_big_even_without_elo_top_sides() -> None:
    no_elo_bigs = SETTINGS.model_copy(update={"agent_big_team_count": 0})
    england_day = day_policy(no_elo_bigs, FMT, on=date(2026, 6, 23))

    assert england_day.phase == "big_group"
    assert england_day.big_teams == ("england",)


def test_phase_ceilings_follow_the_settings_table() -> None:
    assert day_policy(SETTINGS, FMT, on=date(2026, 6, 12)).ceiling_usd == SETTINGS.agent_ceiling_opening_usd
    assert day_policy(SETTINGS, FMT, on=date(2026, 7, 19)).ceiling_usd == SETTINGS.agent_ceiling_qf_final_usd
    assert day_policy(SETTINGS, FMT, on=date(2026, 7, 17)).ceiling_usd == SETTINGS.agent_ceiling_rest_usd


def test_single_game_knockout_days_are_discounted_except_semis_and_final() -> None:
    quarter = day_policy(SETTINGS, FMT, on=date(2026, 7, 10)).ceiling_usd
    semi = day_policy(SETTINGS, FMT, on=date(2026, 7, 15)).ceiling_usd
    final = day_policy(SETTINGS, FMT, on=date(2026, 7, 19)).ceiling_usd

    assert quarter == SETTINGS.agent_ceiling_qf_final_usd - SETTINGS.agent_ceiling_single_game_discount_usd
    assert semi == final == SETTINGS.agent_ceiling_qf_final_usd


def test_ceiling_clamps_to_the_absolute_max() -> None:
    greedy = SETTINGS.model_copy(update={"agent_ceiling_qf_final_usd": 50.0})

    assert day_policy(greedy, FMT, on=date(2026, 7, 19)).ceiling_usd == greedy.agent_run_ceiling_max_usd


def test_phase_knobs_below_the_rest_rate_are_honoured() -> None:
    frugal = SETTINGS.model_copy(update={"agent_ceiling_opening_usd": 1.25})

    assert day_policy(frugal, FMT, on=date(2026, 6, 12)).ceiling_usd == 1.25
