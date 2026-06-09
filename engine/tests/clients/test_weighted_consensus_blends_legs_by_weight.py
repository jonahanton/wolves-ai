from __future__ import annotations

import pytest

from wolves.clients.odds import weighted_consensus

BOOKMAKERS = {"france": 0.20, "spain": 0.30, "england": 0.50}
POLYMARKET = {"france": 0.40, "spain": 0.30, "england": 0.30}


def test_blend_renormalises_to_one():
    blended = weighted_consensus([(BOOKMAKERS, 1.0), (POLYMARKET, 1.0)])
    assert sum(blended.values()) == pytest.approx(1.0, abs=1e-9)


def test_zero_weight_leg_is_ignored():
    blended = weighted_consensus([(BOOKMAKERS, 1.0), (POLYMARKET, 0.0)])
    assert blended == pytest.approx(BOOKMAKERS)


def test_equal_weights_land_between_the_legs_up_to_renormalisation():
    blended = weighted_consensus([(BOOKMAKERS, 1.0), (POLYMARKET, 1.0)])
    for team in BOOKMAKERS:
        lo, hi = sorted((BOOKMAKERS[team], POLYMARKET[team]))
        assert lo - 0.01 <= blended[team] <= hi + 0.01


def test_heavier_leg_pulls_the_blend_toward_it():
    light = weighted_consensus([(BOOKMAKERS, 1.0), (POLYMARKET, 1.0)])
    heavy = weighted_consensus([(BOOKMAKERS, 1.0), (POLYMARKET, 3.0)])
    assert abs(heavy["france"] - POLYMARKET["france"]) < abs(light["france"] - POLYMARKET["france"])


def test_outcome_missing_from_a_leg_uses_the_other_leg_alone():
    blended = weighted_consensus([({"france": 0.5, "spain": 0.5}, 1.0), ({"france": 0.5}, 1.0)])
    assert blended["spain"] == pytest.approx(0.5 / (0.5 + 0.5))
