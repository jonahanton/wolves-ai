from __future__ import annotations

import pytest

from wolves.markets.devig import DevigError, shin_devig


def test_probabilities_sum_to_one() -> None:
    probs = shin_devig([1.85, 4.7, 3.5])
    assert sum(probs) == pytest.approx(1.0)
    assert probs[0] > probs[2] > probs[1]


def test_longshots_shrink_relative_to_proportional() -> None:
    prices = [1.3, 5.0, 21.0]
    implied = [1 / p for p in prices]
    proportional = [q / sum(implied) for q in implied]
    shin = shin_devig(prices)
    assert shin[2] < proportional[2]
    assert shin[0] > proportional[0]


def test_invalid_prices_raise() -> None:
    with pytest.raises(DevigError):
        shin_devig([0.99, 2.0])
