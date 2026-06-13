"""Latent priors reproduce their analytic moments, sampling is deterministic
off the run rng, and a Normal latent matches a DeltaDistribution strength
perturbation on the marginal band (so the slab can retire to a latent)."""

from __future__ import annotations

import numpy as np
import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import DeltaDistribution, Forecaster, StrengthPerturbation
from wolves.sim.latent import LatentEffect, MixturePrior, NormalPrior, SpikeSlabPrior


@pytest.fixture()
def forecaster(tmp_path) -> Forecaster:
    fc = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"))
    fc._state = synthetic_state()
    return fc


@pytest.mark.parametrize(
    ("prior", "exp_mean", "exp_var"),
    [
        (NormalPrior(mean=0.09, sd=0.04), 0.09, 0.04**2),
        (SpikeSlabPrior(p_zero=0.4, mean=0.09, sd=0.04), 0.6 * 0.09, 0.6 * (0.04**2 + 0.09**2) - (0.6 * 0.09) ** 2),
        (
            MixturePrior(
                weights=[0.5, 0.5],
                components=[NormalPrior(mean=-0.1, sd=0.02), NormalPrior(mean=0.1, sd=0.02)],
            ),
            0.0,
            0.02**2 + 0.1**2,
        ),
    ],
)
def test_prior_reproduces_its_moments(prior, exp_mean, exp_var):
    rng = np.random.default_rng(0)
    sample = prior.sample(rng, 200_000)
    assert sample.mean() == pytest.approx(exp_mean, abs=0.003)
    assert sample.var() == pytest.approx(exp_var, rel=0.05)


@pytest.mark.parametrize(
    "prior",
    [
        NormalPrior(mean=0.0, sd=1.0),
        SpikeSlabPrior(p_zero=0.3, mean=0.1, sd=0.05),
        MixturePrior(weights=[0.5, 0.5], components=[NormalPrior(mean=-0.1, sd=0.02), NormalPrior(mean=0.1, sd=0.02)]),
    ],
)
def test_sampling_is_deterministic_off_the_seed(prior):
    a = prior.sample(np.random.default_rng(7), 1000)
    b = prior.sample(np.random.default_rng(7), 1000)
    assert np.array_equal(a, b)


def test_normal_latent_matches_a_delta_distribution_strength(forecaster: Forecaster):
    team = forecaster.fmt.teams[0].id
    via_slab = forecaster.title_probs(
        n_sims=8000,
        seed=3,
        perturbations=(StrengthPerturbation(team=team, delta=DeltaDistribution(mean=0.15, sd=0.08), reason="slab"),),
    )
    result = forecaster.simulate(
        n_sims=8000,
        seed=3,
        latent_effects=(LatentEffect(reason="latent", targets={team: 1.0}, prior=NormalPrior(mean=0.15, sd=0.08)),),
        parameter_uncertainty=False,
    )
    winners = result.ko_winner[max(result.ko_winner)]
    latent_title = float((winners == 0).mean())
    assert latent_title == pytest.approx(via_slab[team], abs=0.02)
