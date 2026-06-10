from __future__ import annotations

import pytest

from wolves.insights.path_tree import team_path_tree


def test_reach_view_decays_through_rounds_and_slots_sum(forecaster) -> None:
    tree = team_path_tree(forecaster, "england", n_sims=8000, seed=4)

    p_play = [stage.p_play for stage in tree.stages]
    assert p_play == sorted(p_play, reverse=True)
    assert sum(tree.qualification.values()) == pytest.approx(1.0, abs=0.01)
    r32 = tree.stages[0]
    assert sum(slot.share for slot in r32.slots) == pytest.approx(r32.p_play, abs=0.01)


def test_title_view_conditions_on_winning(forecaster) -> None:
    tree = team_path_tree(forecaster, "england", view="title", n_sims=8000, seed=4)

    final = next(stage for stage in tree.stages if stage.stage == "final")
    assert final.p_play == pytest.approx(1.0)
    assert final.p_advance_given_play == pytest.approx(1.0)
