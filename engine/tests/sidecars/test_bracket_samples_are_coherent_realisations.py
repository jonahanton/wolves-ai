from __future__ import annotations

from wolves.sidecars import DEFAULT_BRACKET_SAMPLES, build_bracket_samples


def test_samples_carry_valid_teams_and_internally_consistent_winners(inputs):
    payload = build_bracket_samples(inputs)
    team_ids = {t.id for t in inputs.fmt.teams}
    n_knockout = len(inputs.fmt.knockout)
    assert len(payload.samples) == DEFAULT_BRACKET_SAMPLES
    for sample in payload.samples:
        assert sample.world in inputs.weights
        assert len(sample.matches) == n_knockout
        winners = {m.match: m.winner for m in sample.matches}
        for m in sample.matches:
            assert {m.home, m.away, m.winner} <= team_ids
            assert m.winner in (m.home, m.away)
        for km in inputs.fmt.knockout:
            entry = next(m for m in sample.matches if m.match == km.match)
            for side, spec in (("home", km.home), ("away", km.away)):
                if spec.startswith("W"):
                    assert getattr(entry, side) == winners[int(spec[1:])]


def test_sample_count_is_a_knob(inputs):
    assert len(build_bracket_samples(inputs, n_samples=7).samples) == 7
