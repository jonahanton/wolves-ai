from __future__ import annotations

import pytest

from wolves.config import Settings
from wolves.run import generate_snapshot


@pytest.fixture(scope="module")
def snapshot():
    return generate_snapshot(Settings(), n_sims=2000, seed=42)


def test_finish_probabilities_sum_to_one(snapshot):
    assert sum(snapshot.england.finish_probs.values()) == pytest.approx(1.0, abs=0.01)


def test_reach_probabilities_decrease_monotonically(snapshot):
    probs = [snapshot.england.reach_probs[k] for k in ("r32", "r16", "qf", "sf", "final", "champion")]
    assert probs == sorted(probs, reverse=True)


def test_every_knockout_slot_has_candidates(snapshot):
    assert len(snapshot.slots) == 32
    for slot in snapshot.slots:
        assert slot.home.candidates and slot.away.candidates


def test_england_win_group_path_goes_through_atlanta(snapshot):
    win = next(p for p in snapshot.england.paths if p.finish == "win_group")
    assert win.r32_match == 80
    assert win.city == "Atlanta"
