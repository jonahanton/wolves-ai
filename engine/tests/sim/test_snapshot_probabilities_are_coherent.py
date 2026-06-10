from __future__ import annotations

import pytest


def test_finish_probabilities_sum_to_one(snapshot):
    assert sum(snapshot.focus.finish_probs.values()) == pytest.approx(1.0, abs=0.01)


def test_reach_probabilities_decrease_monotonically(snapshot):
    probs = [snapshot.focus.reach_probs[k] for k in ("r32", "r16", "qf", "sf", "final", "champion")]
    assert probs == sorted(probs, reverse=True)


def test_every_knockout_slot_has_candidates(snapshot):
    assert len(snapshot.slots) == 32
    for slot in snapshot.slots:
        assert slot.home.candidates and slot.away.candidates


def test_focus_team_win_group_path_goes_through_atlanta(snapshot):
    win = next(p for p in snapshot.focus.paths if p.finish == "win_group")
    assert win.r32_match == 80
    assert win.city == "Atlanta"
