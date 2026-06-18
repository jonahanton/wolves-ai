from __future__ import annotations

import pytest

from wolves.insights.impact import DISPLAY_FLOOR_PP, stage_impacts

AGENT = {"r32": 0.95, "champion": 0.10}


def test_subfloor_ingame_move_is_collapsed_to_no_shift():
    then = {"r32": 0.90, "champion": 0.07}
    now = {"r32": 0.90, "champion": 0.07}
    # A held leg a hair above now: the raw in-game move is well under the floor.
    held = {"r32": 0.90, "champion": 0.0701}
    champion = stage_impacts(AGENT, then, now, held)["champion"]
    assert champion["from_ingame_pp"] == 0.0
    assert champion["estimated"] == champion["after_results"]


@pytest.mark.parametrize("held_champion", [0.090, 0.110, 0.140])
def test_a_larger_held_leg_never_reports_a_smaller_uplift(held_champion):
    then = {"r32": 0.90, "champion": 0.06}
    now = {"r32": 0.90, "champion": 0.07}
    held = {"r32": 0.96, "champion": held_champion}
    smaller = stage_impacts(AGENT, then, now, {**held, "champion": held_champion - 0.01})["champion"]
    larger = stage_impacts(AGENT, then, now, held)["champion"]
    assert larger["from_ingame_pp"] >= smaller["from_ingame_pp"] - DISPLAY_FLOOR_PP
