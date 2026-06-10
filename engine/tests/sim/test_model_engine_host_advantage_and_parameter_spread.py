from __future__ import annotations

import numpy as np
import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.sim.model_engine import PoissonMatchEngine


def _city_in(country: str) -> str:
    return next(v.city for v in FMT.venues if v.country == country)


def test_host_nation_gets_home_advantage_only_at_home() -> None:
    engine = PoissonMatchEngine(FMT, synthetic_state())
    n = 8
    engine.begin(np.random.default_rng(0), n)
    mexico = next(i for i, t in enumerate(FMT.teams) if t.id == "mexico")
    england = next(i for i, t in enumerate(FMT.teams) if t.id == "england")
    home = np.full(n, mexico, dtype=np.intp)
    away = np.full(n, england, dtype=np.intp)

    at_home, _ = engine.lambdas(home, away, city=_city_in("MEX"), stage="group")
    in_usa, _ = engine.lambdas(home, away, city=_city_in("USA"), stage="group")

    assert at_home[0] > in_usa[0]


def test_covariance_spreads_rates_across_worlds_and_its_absence_does_not() -> None:
    state = synthetic_state()
    with_cov = synthetic_state()
    object.__setattr__(with_cov, "covariance", np.eye(len(state.teams) + 2) * 0.01)

    n = 64
    home = np.zeros(n, dtype=np.intp)
    away = np.full(n, 1, dtype=np.intp)
    city = FMT.venues[0].city

    flat = PoissonMatchEngine(FMT, state)
    flat.begin(np.random.default_rng(3), n)
    lam_flat, _ = flat.lambdas(home, away, city=city, stage="group")

    spread = PoissonMatchEngine(FMT, with_cov)
    spread.begin(np.random.default_rng(3), n)
    lam_spread, _ = spread.lambdas(home, away, city=city, stage="group")

    assert np.ptp(lam_flat) == pytest.approx(0.0)
    assert np.ptp(lam_spread) > 0.01
