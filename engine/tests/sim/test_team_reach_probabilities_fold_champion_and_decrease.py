from __future__ import annotations

import pytest

REACH_KEYS = ("r32", "r16", "qf", "sf", "final", "champion")


def test_every_team_has_a_monotone_reach_ladder_folding_champion(snapshot):
    assert len(snapshot.teams) == 48
    for team in snapshot.teams:
        ladder = [team.reach_probs[k] for k in REACH_KEYS]
        assert ladder == sorted(ladder, reverse=True), team.team_id
        assert team.champion_prob == team.reach_probs["champion"]


def test_reach_probabilities_total_the_round_sizes(snapshot):
    for key, size in (("r32", 32), ("r16", 16), ("qf", 8), ("sf", 4), ("final", 2), ("champion", 1)):
        total = sum(t.reach_probs[key] for t in snapshot.teams)
        assert total == pytest.approx(size, abs=0.05), key
