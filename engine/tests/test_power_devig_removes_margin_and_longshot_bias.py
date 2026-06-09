from __future__ import annotations

import pytest

from wolves.clients.odds import DevigError, blend_abilities, consensus_probabilities, power_devig


def test_devigged_probabilities_sum_to_one():
    probs = power_devig([1.85, 4.7, 3.5])
    assert sum(probs) == pytest.approx(1.0, abs=1e-9)
    assert all(0 < p < 1 for p in probs)


def test_fair_prices_pass_through_unchanged():
    probs = power_devig([2.0, 2.0])
    assert probs == pytest.approx([0.5, 0.5], abs=1e-6)


def test_power_method_shrinks_longshots_harder_than_proportional():
    prices = [1.25, 5.5, 15.0]
    devigged = power_devig(prices)
    implied = [1 / p for p in prices]
    proportional = [q / sum(implied) for q in implied]
    assert devigged[2] < proportional[2]
    assert devigged[0] > proportional[0]


def test_invalid_prices_raise_with_context():
    with pytest.raises(DevigError) as exc_info:
        power_devig([0.95, 2.0])
    assert exc_info.value.prices == [0.95, 2.0]


def test_consensus_averages_in_log_odds_and_renormalises():
    consensus = consensus_probabilities(
        [
            {"England": 0.5, "Croatia": 0.2, "Draw": 0.3},
            {"England": 0.5, "Croatia": 0.2, "Draw": 0.3},
        ]
    )
    assert consensus["England"] == pytest.approx(0.5, abs=1e-9)
    assert sum(consensus.values()) == pytest.approx(1.0, abs=1e-9)


def test_lambda_blend_moves_abilities_toward_market_and_leaves_unpriced_teams():
    model = {"england": 2000.0, "ghana": 1700.0, "panama": 1600.0}
    market = {"england": 0.14, "ghana": 0.001}
    blended = blend_abilities(model, market, lam=0.3)
    assert blended["england"] > blended["ghana"]
    assert blended["panama"] == 1600.0
    no_blend = blend_abilities(model, market, lam=0.0)
    assert no_blend["england"] == pytest.approx(2000.0)
