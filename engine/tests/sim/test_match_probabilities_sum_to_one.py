from __future__ import annotations

import re

import pytest

SCORELINE = re.compile(r"^\d+-\d+$")


def test_every_unplayed_match_has_an_entry(snapshot):
    assert len(snapshot.matches) == 104
    assert len({m.match for m in snapshot.matches}) == 104


def test_group_match_outcomes_sum_to_one(snapshot):
    group = [m for m in snapshot.matches if m.stage == "group"]
    assert len(group) == 72
    for m in group:
        assert m.p_draw is not None and m.p_pairing is None and m.p_decided_90 is None
        assert m.p_home + m.p_draw + m.p_away == pytest.approx(1.0, abs=0.001)


def test_knockout_tie_outcomes_sum_to_one(snapshot):
    knockout = [m for m in snapshot.matches if m.stage != "group"]
    assert len(knockout) == 32
    for m in knockout:
        assert m.p_draw is None
        assert m.p_home + m.p_away == pytest.approx(1.0, abs=0.001)
        assert m.p_decided_90 is not None and 0.0 <= m.p_decided_90 <= 1.0


def test_modal_scoreline_is_recorded_for_every_match(snapshot):
    for m in snapshot.matches:
        assert m.modal_score is not None and SCORELINE.match(m.modal_score)
