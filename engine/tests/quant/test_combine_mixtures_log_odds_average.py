"""combine_mixtures is a weighted log-odds average renormalised to a partition.
Pinned against a hand-computed two-input case so a refactor cannot drift it into
a plain arithmetic mean."""

from __future__ import annotations

from wolves.logodds import from_log_odds, to_log_odds
from wolves.quant.wolves_quant import combine_mixtures


def test_two_input_average_matches_hand_computation():
    a = {"spain": 0.2, "france": 0.1, "rest": 0.7}
    b = {"spain": 0.4, "france": 0.1, "rest": 0.5}

    combined = combine_mixtures([a, b])

    raw = {team: from_log_odds(0.5 * (to_log_odds(a[team]) + to_log_odds(b[team]))) for team in a}
    norm = sum(raw.values())
    expected = {team: p / norm for team, p in raw.items()}
    assert combined.keys() == expected.keys()
    for team, p in expected.items():
        assert abs(combined[team] - p) < 1e-9


def test_renormalises_to_one():
    combined = combine_mixtures(
        [{"a": 0.5, "b": 0.3, "c": 0.2}, {"a": 0.1, "b": 0.6, "c": 0.3}], weights=[2.0, 1.0]
    )
    assert abs(sum(combined.values()) - 1.0) < 1e-9
