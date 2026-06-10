from __future__ import annotations

import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import DeltaDistribution, Forecaster, StrengthPerturbation


@pytest.fixture()
def forecaster(tmp_path) -> Forecaster:
    instance = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    instance._state = synthetic_state()
    return instance


def test_zero_sd_reduces_exactly_to_the_point_delta(forecaster: Forecaster):
    team = forecaster.state.teams[0]
    point = forecaster.title_probs(
        n_sims=2000, seed=0, perturbations=(StrengthPerturbation(team=team, delta=0.2, reason="point"),)
    )
    spread = forecaster.title_probs(
        n_sims=2000,
        seed=0,
        perturbations=(StrengthPerturbation(team=team, delta=DeltaDistribution(mean=0.2, sd=0.0), reason="dist"),),
    )
    assert spread == point


def test_magnitude_uncertainty_survives_title_probs(forecaster: Forecaster):
    """title_probs strips MODEL covariance; the perturbation's own variance must not be stripped."""
    team = forecaster.state.teams[0]
    point = forecaster.title_probs(
        n_sims=2000, seed=0, perturbations=(StrengthPerturbation(team=team, delta=0.2, reason="point"),)
    )
    spread = forecaster.title_probs(
        n_sims=2000,
        seed=0,
        perturbations=(StrengthPerturbation(team=team, delta=DeltaDistribution(mean=0.2, sd=0.3), reason="dist"),),
    )
    assert spread != point
    assert abs(sum(spread.values()) - 1.0) < 1e-6


def test_negative_sd_is_rejected():
    with pytest.raises(ValueError):
        DeltaDistribution(mean=0.1, sd=-0.1)
