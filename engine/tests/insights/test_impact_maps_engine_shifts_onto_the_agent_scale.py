from __future__ import annotations

import pytest

from wolves.insights.impact import estimated_stages, exit_distribution, shifted, stage_impacts

AGENT = {"r32": 0.95, "champion": 0.10}


def test_equal_legs_leave_the_published_number_alone():
    assert shifted(0.10, 0.07, 0.07) == pytest.approx(0.10)


def test_shift_direction_and_scale_respect_log_odds():
    up = shifted(0.10, 0.07, 0.14)
    down = shifted(0.10, 0.07, 0.035)
    assert up > 0.10 > down
    assert up < 0.25


def test_extreme_legs_stay_inside_the_unit_interval():
    assert 0.0 < shifted(0.999, 0.0001, 0.9999) < 1.0
    assert 0.0 < shifted(0.001, 0.9999, 0.0001) < 1.0


def test_components_split_sequentially_and_sum_to_the_estimate():
    then = {"r32": 0.90, "champion": 0.06}
    now = {"r32": 0.92, "champion": 0.07}
    held = {"r32": 0.96, "champion": 0.09}
    impacts = stage_impacts(AGENT, then, now, held)
    champion = impacts["champion"]
    assert champion["agent"] == 0.10
    assert champion["after_results"] > champion["agent"]
    assert champion["from_results_pp"] > 0
    assert champion["from_ingame_pp"] > champion["from_results_pp"]
    assert champion["display_floor_pp"] == 0.5
    total = champion["agent"] + (champion["from_results_pp"] + champion["from_ingame_pp"]) / 100
    assert champion["estimated"] == pytest.approx(total, abs=0.011)
    assert set(impacts) == {"r32", "champion"}


def test_series_point_shifts_the_full_then_to_point_leg():
    point = estimated_stages(AGENT, {"r32": 0.90, "champion": 0.06}, {"r32": 0.90, "champion": 0.12})
    assert point["r32"] == pytest.approx(0.95)
    assert point["champion"] > 0.10


def test_exit_distribution_projects_reach_without_moving_champion():
    exits = exit_distribution({"r32": 0.7, "r16": 0.72, "qf": 0.45, "sf": 0.3, "final": 0.18, "champion": 0.2})
    assert exits["champion"] == pytest.approx(0.2)
    assert min(exits.values()) >= 0
    assert sum(exits.values()) == pytest.approx(1.0)
