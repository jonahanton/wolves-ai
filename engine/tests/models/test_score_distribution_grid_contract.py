from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from wolves.models.contracts import Fixture, UnknownModelTeamError
from wolves.models.poisson import PoissonDecayModel, poisson_grid


def test_grid_normalises_and_outcomes_partition(fixture_dataset) -> None:
    model = PoissonDecayModel()
    state = model.fit(fixture_dataset, as_of=date(2026, 1, 1))

    dist = model.score_distribution(Fixture(home="alpha", away="delta"), state)
    assert dist.grid.sum() == pytest.approx(1.0)
    assert sum(dist.outcome_probs()) == pytest.approx(1.0)
    assert dist.p_home > dist.p_away

    flipped = model.score_distribution(Fixture(home="delta", away="alpha"), state)
    assert flipped.p_away == pytest.approx(dist.p_home)


def test_neutral_fixtures_carry_no_home_advantage(fixture_dataset) -> None:
    model = PoissonDecayModel()
    state = model.fit(fixture_dataset, as_of=date(2026, 1, 1))

    neutral = model.rates(Fixture(home="alpha", away="beta", neutral=True), state)
    at_home = model.rates(Fixture(home="alpha", away="beta", neutral=False), state)
    assert at_home[0] > neutral[0]
    assert at_home[1] == pytest.approx(neutral[1])


def test_unknown_team_raises(fixture_dataset) -> None:
    model = PoissonDecayModel()
    state = model.fit(fixture_dataset, as_of=date(2026, 1, 1))

    with pytest.raises(UnknownModelTeamError):
        model.score_distribution(Fixture(home="alpha", away="narnia"), state)


def test_intensity_scales_rates_for_extra_time() -> None:
    full = poisson_grid(1.5, 1.2)
    third = poisson_grid(0.5, 0.4)
    goals = np.arange(full.grid.shape[0])
    assert (goals * third.grid.sum(axis=1)).sum() == pytest.approx((goals * full.grid.sum(axis=1)).sum() / 3, rel=0.01)
