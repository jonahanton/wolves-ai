from __future__ import annotations

import numpy as np

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import FMT, synthetic_state
from wolves.data.teams import registry_team_key
from wolves.models.poisson import knockout_advance_draws
from wolves.sim.model_engine import ET_INTENSITY, PoissonMatchEngine


def test_closed_form_advance_matches_the_engine_shootout_resolution() -> None:
    """The analytic advance probability must reproduce the engine's own resolution; a
    stronger home side separates the centre from an even split so the check has teeth."""
    strong = registry_team_key(FMT.teams[0].id)
    engine = PoissonMatchEngine(FMT, synthetic_state({strong: 0.3}))
    n = 200_000
    engine.begin(np.random.default_rng(1), n)
    home = np.zeros(n, dtype=np.intp)
    away = np.full(n, 1, dtype=np.intp)
    city = FMT.venues[0].city

    lam_h, lam_a = engine.lambdas(home, away, city=city, stage="knockout")
    hg, ag = engine.simulate_goals(np.random.default_rng(2), lam_h, lam_a)
    sim = float(engine.knockout_home_wins(np.random.default_rng(3), home, away, hg, ag, city=city).mean())

    p_home, p_away = knockout_advance_draws(lam_h, lam_a, lam_h * ET_INTENSITY, lam_a * ET_INTENSITY)
    assert np.allclose(p_home + p_away, 1.0)
    assert 0.52 < p_home.mean() < 0.70
    assert abs(float(p_home.mean()) - sim) < 0.005
