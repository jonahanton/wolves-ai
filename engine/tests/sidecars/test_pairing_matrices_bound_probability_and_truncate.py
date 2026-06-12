from __future__ import annotations

from wolves.sidecars import KO_ROUNDS, TOP_OPPONENTS, build_pairing_matrices

TOLERANCE = 1e-6


def test_rows_are_descending_truncated_and_sum_to_at_most_one(inputs):
    payload = build_pairing_matrices(inputs)
    assert set(payload.rounds) == set(KO_ROUNDS)
    for per_team in payload.rounds.values():
        for entries in per_team.values():
            assert len(entries) <= TOP_OPPONENTS
            probs = [e.p for e in entries]
            assert probs == sorted(probs, reverse=True)
            assert all(p > 0 for p in probs)
            assert sum(probs) <= 1.0 + TOLERANCE


def test_r32_pairings_are_symmetric(inputs):
    rows = build_pairing_matrices(inputs).rounds["r32"]
    for team, entries in rows.items():
        top = entries[0]
        reverse = {e.opponent: e.p for e in rows[top.opponent]}
        assert team in reverse
        assert abs(reverse[team] - top.p) < 1e-3
