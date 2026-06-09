from __future__ import annotations

import pytest

from wolves.agent.consensus import median_overrides
from wolves.agent.contracts import RatingOverride


def _override(team: str, delta: float) -> RatingOverride:
    return RatingOverride(team_id=team, delta_elo=delta, cause="c", ledger_ids=["led-0001"])


def test_per_team_median_with_missing_samples_counting_as_zero():
    samples = [
        [_override("england", 15.0), _override("france", -8.0)],
        [_override("england", 21.0)],
        [_override("england", 9.0), _override("france", -6.0)],
    ]
    medians, disagreement = median_overrides(samples)
    by_team = {o.team_id: o.delta_elo for o in medians}

    assert by_team["england"] == 15.0
    assert by_team["france"] == -6.0
    assert disagreement.k == 3
    assert disagreement.per_team_spread["england"] == 12.0
    assert disagreement.per_team_spread["france"] == 8.0
    assert disagreement.max_spread == 12.0


def test_median_keeps_citations_from_a_real_sample():
    samples = [[_override("england", 10.0)], [_override("england", 20.0)], [_override("england", 30.0)]]
    medians, _ = median_overrides(samples)
    assert medians[0].ledger_ids == ["led-0001"]


def test_zero_median_overrides_are_dropped():
    samples = [[_override("spain", 5.0)], [], []]
    medians, disagreement = median_overrides(samples)
    assert medians == []
    assert disagreement.per_team_spread["spain"] == 5.0


def test_no_samples_yield_empty_consensus():
    medians, disagreement = median_overrides([])
    assert medians == []
    assert disagreement.k == 0
    assert disagreement.mean_spread == pytest.approx(0.0)
