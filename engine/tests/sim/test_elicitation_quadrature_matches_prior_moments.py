"""The discrete quadrature the elicitation A/B scores against the continuous
latent must be a faithful quadrature of the prior: its node weights integrate
to one and recover the prior's mean and variance, and the spike-slab split
carries the zero mass at p_zero. If these drift, the A/B compares the latent
against something other than its own quadrature and the verdict is meaningless."""

from __future__ import annotations

import numpy as np
import pytest

from wolves.sim.elicitation import gauss_hermite_worlds, spike_slab_worlds


@pytest.mark.parametrize("nodes", [2, 3, 5])
def test_gauss_hermite_nodes_recover_the_normal_moments(nodes: int):
    mean, sd = 0.12, 0.06
    worlds = gauss_hermite_worlds(mean=mean, sd=sd, nodes=nodes)
    weights = np.array([w.weight for w in worlds])
    deltas = np.array([w.delta for w in worlds])
    assert weights.sum() == pytest.approx(1.0)
    assert (weights * deltas).sum() == pytest.approx(mean, abs=1e-9)
    var = (weights * (deltas - mean) ** 2).sum()
    assert var == pytest.approx(sd**2, rel=1e-6)


def test_spike_slab_carries_the_zero_mass_at_p_zero():
    worlds = spike_slab_worlds(p_zero=0.4, mean=0.15, sd=0.05, nodes=3)
    weights = np.array([w.weight for w in worlds])
    zero_mass = sum(w.weight for w in worlds if w.delta == 0.0)
    assert weights.sum() == pytest.approx(1.0)
    assert zero_mass == pytest.approx(0.4, abs=1e-9)
