from __future__ import annotations

TOLERANCE = 1e-9


def test_modal_pairing_probability_is_bounded_by_slot_candidate_marginals(snapshot):
    slots = {s.match: s for s in snapshot.slots}
    for m in snapshot.matches:
        if m.stage == "group":
            continue
        slot = slots[m.match]
        home = {c.team_id: c.prob for c in slot.home.candidates}
        away = {c.team_id: c.prob for c in slot.away.candidates}
        assert m.p_pairing is not None and 0.0 < m.p_pairing <= 1.0
        assert m.home_id in home and m.away_id in away
        assert m.p_pairing <= home[m.home_id] + TOLERANCE
        assert m.p_pairing <= away[m.away_id] + TOLERANCE
