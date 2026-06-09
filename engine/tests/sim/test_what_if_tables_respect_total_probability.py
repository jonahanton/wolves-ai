from __future__ import annotations

import pytest

from wolves.sim.api import run_simulation


@pytest.fixture(scope="module")
def england():
    return run_simulation({}, {}, 4000, 11).england


def test_outcome_probs_sum_to_one_per_fixture(england):
    for fixture in england.what_if:
        assert sum(o.prob for o in fixture.outcomes) == pytest.approx(1.0, abs=0.001)


def test_conditional_finish_probs_recover_unconditional_marginals(england):
    for fixture in england.what_if:
        for finish, marginal in england.finish_probs.items():
            mixed = sum(o.prob * o.finish_probs[finish] for o in fixture.outcomes)
            assert mixed == pytest.approx(marginal, abs=0.002), (fixture.match, finish)


def test_conditional_city_probs_recover_unconditional_r32_cities(england):
    r32_cities = {c.city: c.prob for c in england.city_probs["r32"]}
    for fixture in england.what_if:
        for city, marginal in r32_cities.items():
            mixed = sum(o.prob * o.r32_city_probs.get(city, 0.0) for o in fixture.outcomes)
            assert mixed == pytest.approx(marginal, abs=0.002), (fixture.match, city)
