from __future__ import annotations

import pytest

FINISH_KEYS = ("win_group", "runner_up", "third_qualified", "third_eliminated", "fourth")


def test_each_team_finish_distribution_sums_to_one(snapshot):
    assert len(snapshot.groups) == 12
    for block in snapshot.groups:
        assert len(block.teams) == 4
        for team in block.teams:
            assert set(team.finish_probs) == set(FINISH_KEYS)
            assert sum(team.finish_probs.values()) == pytest.approx(1.0, abs=0.01)


@pytest.mark.parametrize(
    ("position", "keys"),
    [
        ("first", ("win_group",)),
        ("second", ("runner_up",)),
        ("third", ("third_qualified", "third_eliminated")),
        ("fourth", ("fourth",)),
    ],
)
def test_each_group_position_is_filled_by_exactly_one_team(snapshot, position, keys):
    for block in snapshot.groups:
        total = sum(team.finish_probs[k] for team in block.teams for k in keys)
        assert total == pytest.approx(1.0, abs=0.01), (block.group, position)


def test_expected_points_are_within_group_stage_bounds(snapshot):
    for block in snapshot.groups:
        group_total = sum(team.expected_points for team in block.teams)
        assert 12.0 <= group_total <= 18.0
        for team in block.teams:
            assert 0.0 <= team.expected_points <= 9.0
