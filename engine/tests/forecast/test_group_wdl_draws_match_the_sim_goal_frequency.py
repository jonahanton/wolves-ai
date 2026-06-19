from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import Forecaster, StrengthPerturbation
from wolves.models.poisson import poisson_wdl_draws
from wolves.sim.model_engine import PARAMETER_DRAWS

# Mexico host Mexico (acclimatised, altitude 1566m), so both home advantage and
# the altitude bonus ride this fixture; dropping either shifts p_home well past
# the Monte-Carlo floor, giving the negative control clean separation.
HOST_FIXTURE = 28
NEUTRAL_FIXTURE = 50
SIMS_PER_DRAW = 600
SEED = 7
WEIGHTS = {"base": 0.7, "shift": 0.3}


@pytest.fixture(scope="module")
def forecaster() -> Forecaster:
    base = synthetic_state()
    cov = np.eye(len(base.strengths) + 2) * 0.03
    instance = Forecaster(Settings(storage_mode="local"))
    instance._state = dataclasses.replace(base, covariance=cov)
    return instance


def _worlds() -> dict[str, tuple]:
    shift = StrengthPerturbation(team="mexico", delta=0.2, reason="test")
    return {"base": ((), ()), "shift": ((shift,), ())}


def _sim_frequency(forecaster: Forecaster, match: int) -> np.ndarray:
    """Per-draw weighted W/D/L frequency from the real tournament sim, bucketed
    exactly as the old sidecar did (sim i feeds parameter draw i % PARAMETER_DRAWS)."""
    n_sims = PARAMETER_DRAWS * SIMS_PER_DRAW
    draw_idx = np.arange(n_sims) % PARAMETER_DRAWS
    counts = np.maximum(np.bincount(draw_idx, minlength=PARAMETER_DRAWS), 1)
    mixed = np.zeros(PARAMETER_DRAWS)
    for name, weight in WEIGHTS.items():
        perturbations, _ = _worlds()[name]
        result = forecaster.simulate(n_sims=n_sims, seed=SEED, perturbations=perturbations, results={})
        hg, ag = result.group_goals[match]
        mixed += weight * np.bincount(draw_idx, weights=hg > ag, minlength=PARAMETER_DRAWS) / counts
    return mixed


def test_analytic_curve_centre_matches_the_sim_goal_frequency(forecaster: Forecaster) -> None:
    """The analytic curve must reproduce the published group number, which is the
    sim's goal frequency, not the neutral match grid. Verified on a host-city
    fixture so home advantage and altitude are both exercised."""
    curves = forecaster.group_wdl_draws(
        worlds=_worlds(), weights=WEIGHTS, played=frozenset(), draws=PARAMETER_DRAWS, seed=SEED
    )
    for match in (HOST_FIXTURE, NEUTRAL_FIXTURE):
        analytic = np.array(curves[match][0])
        sim = _sim_frequency(forecaster, match)
        assert abs(analytic.mean() - sim.mean()) < 0.01
        rms = float(np.sqrt(np.mean((analytic - sim) ** 2)))
        assert rms < 4.0 / np.sqrt(SIMS_PER_DRAW)


def test_dropping_city_advantage_breaks_the_parity_on_the_host_fixture(forecaster: Forecaster) -> None:
    """Negative control: a city-blind curve (neutral rates, no host advantage or
    altitude) drifts the centre well past the noise floor, so the parity check
    has teeth and would catch the regression."""
    sim = _sim_frequency(forecaster, HOST_FIXTURE)
    spec = next(m for m in forecaster.fmt.group_matches if m.match == HOST_FIXTURE)
    lam_home, lam_away = forecaster.match_rates(spec.home, spec.away, neutral=True)
    blind_home, _, _ = poisson_wdl_draws(np.full(PARAMETER_DRAWS, lam_home), np.full(PARAMETER_DRAWS, lam_away))
    assert abs(float(blind_home.mean()) - sim.mean()) > 0.05
