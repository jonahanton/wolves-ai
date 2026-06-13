"""Elicitation A/B: does a few-world discrete quadrature recover the same
calibration as sampling a continuous latent prior inside the MC loop?

The discrete worlds are a K-point quadrature of the continuous-news integral:
each world is one node, its weight the quadrature mass. This harness expresses
one elicited belief both ways, generates held-out tournaments by sampling the
true effect from the prior, and scores both forecasts' title vectors by
log-loss on the realised champions. With no live result backlog yet, the prior
is the data-generating truth for the news effect, so the comparison is fair:
both forecasts see the same realised outcomes and the continuous one is the
correctly specified estimator, not a trivially perfect oracle. The same scoring
applies unchanged once live matches resolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from wolves.sim.latent import LatentEffect, NormalPrior, SpikeSlabPrior

if TYPE_CHECKING:
    from wolves.forecast import Perturbation
    from wolves.sim.format import FormatData
    from wolves.sim.mc import SimResult


class ElicitationForecaster(Protocol):
    fmt: FormatData

    def simulate(
        self,
        *,
        n_sims: int = ...,
        seed: int = ...,
        perturbations: tuple[Perturbation, ...] = ...,
        latent_effects: tuple[LatentEffect, ...] = ...,
        parameter_uncertainty: bool = ...,
    ) -> SimResult: ...


@dataclass(frozen=True)
class QuadratureWorld:
    """One node of a discrete quadrature of a continuous prior: a strength delta
    and the quadrature mass that approximates the prior's density there."""

    delta: float
    weight: float


@dataclass(frozen=True)
class ABResult:
    """Held-out log-loss of the discrete quadrature against the continuous
    latent, plus each forecast's dispersion (the title-vector entropy in nats);
    a higher discrete loss or lower discrete entropy is the under-dispersion the
    continuous form removes."""

    team: str
    n_nodes: int
    discrete_log_loss: float
    continuous_log_loss: float
    discrete_entropy: float
    continuous_entropy: float
    truth_entropy: float

    @property
    def discrete_excess_loss(self) -> float:
        return self.discrete_log_loss - self.continuous_log_loss


def gauss_hermite_worlds(*, mean: float, sd: float, nodes: int) -> list[QuadratureWorld]:
    """Gauss-Hermite quadrature of Normal(mean, sd) as weighted strength nodes."""
    if sd == 0.0 or nodes == 1:
        return [QuadratureWorld(delta=mean, weight=1.0)]
    raw_nodes, raw_weights = np.polynomial.hermite_e.hermegauss(nodes)
    weights = raw_weights / np.sqrt(2.0 * np.pi)
    return [
        QuadratureWorld(delta=float(mean + sd * x), weight=float(w))
        for x, w in zip(raw_nodes, weights, strict=True)
    ]


def spike_slab_worlds(*, p_zero: float, mean: float, sd: float, nodes: int) -> list[QuadratureWorld]:
    """A zero node at mass p_zero plus the slab's Gauss-Hermite nodes at 1 - p_zero."""
    slab = gauss_hermite_worlds(mean=mean, sd=sd, nodes=nodes)
    worlds = [QuadratureWorld(delta=0.0, weight=p_zero)]
    worlds += [QuadratureWorld(delta=w.delta, weight=(1.0 - p_zero) * w.weight) for w in slab]
    return worlds


def _title_vector(result: SimResult, n_teams: int) -> np.ndarray:
    winners = result.ko_winner[max(result.ko_winner)]
    counts = np.bincount(winners, minlength=n_teams).astype(np.float64)
    return counts / counts.sum()


def _strength_world(
    forecaster: ElicitationForecaster, team: str, delta: float, *, n_sims: int, seed: int
) -> np.ndarray:
    from wolves.forecast import StrengthPerturbation

    pert = (StrengthPerturbation(team=team, delta=delta, reason="elicitation"),) if delta != 0.0 else ()
    result = forecaster.simulate(n_sims=n_sims, seed=seed, perturbations=pert, parameter_uncertainty=False)
    return _title_vector(result, len(forecaster.fmt.teams))


def compare(
    forecaster: ElicitationForecaster,
    *,
    team: str,
    prior: NormalPrior | SpikeSlabPrior,
    nodes: int,
    n_truth: int = 64,
    n_sims: int = 8_000,
    seed: int = 0,
) -> ABResult:
    """Score a discrete K-node quadrature of prior against the continuous latent
    on held-out tournaments whose true effect is drawn from the same prior."""
    fmt_teams = [t.id for t in forecaster.fmt.teams]
    n_teams = len(fmt_teams)
    if team not in fmt_teams:
        raise ValueError(f"team {team!r} is not in the tournament format")

    if isinstance(prior, SpikeSlabPrior):
        worlds = spike_slab_worlds(p_zero=prior.p_zero, mean=prior.mean, sd=prior.sd, nodes=nodes)
    else:
        worlds = gauss_hermite_worlds(mean=prior.mean, sd=prior.sd, nodes=nodes)

    discrete = np.zeros(n_teams)
    for i, w in enumerate(worlds):
        discrete += w.weight * _strength_world(forecaster, team, w.delta, n_sims=n_sims, seed=seed + i)
    discrete /= sum(w.weight for w in worlds)

    latent = (LatentEffect(reason="elicitation", targets={team: 1.0}, prior=prior),)
    continuous = _title_vector(
        forecaster.simulate(n_sims=n_sims, seed=seed, latent_effects=latent, parameter_uncertainty=False),
        n_teams,
    )

    rng = np.random.default_rng(seed)
    truths = prior.sample(rng, n_truth)
    champions = np.array(
        [rng.choice(n_teams, p=_strength_world(forecaster, team, float(d), n_sims=n_sims, seed=seed + 1000 + i))
         for i, d in enumerate(truths)]
    )
    truth_dist = np.bincount(champions, minlength=n_teams).astype(np.float64) / n_truth

    return ABResult(
        team=team,
        n_nodes=len(worlds),
        discrete_log_loss=_cross_entropy(truth_dist, discrete),
        continuous_log_loss=_cross_entropy(truth_dist, continuous),
        discrete_entropy=_entropy(discrete),
        continuous_entropy=_entropy(continuous),
        truth_entropy=_entropy(truth_dist),
    )


@dataclass(frozen=True)
class MultiDriverResult:
    """The combinatorial case the continuous form is for: M independent drivers
    need K**M discrete worlds, truncated at the lattice cap, while the continuous
    latents ride one set of draws. discrete_excess_loss above the noise floor is
    the under-dispersion a truncated lattice cannot avoid."""

    n_drivers: int
    nodes_each: int
    lattice_worlds: int
    capped_worlds: int
    discrete_log_loss: float
    continuous_log_loss: float

    @property
    def discrete_excess_loss(self) -> float:
        return self.discrete_log_loss - self.continuous_log_loss


def compare_multi_driver(
    forecaster: ElicitationForecaster,
    *,
    teams: list[str],
    prior: NormalPrior,
    nodes: int,
    lattice_cap: int = 24,
    n_truth: int = 64,
    n_sims: int = 8_000,
    seed: int = 0,
) -> MultiDriverResult:
    """Score the truncated discrete lattice of M independent single-team priors
    against the M continuous latents, on held-out tournaments drawn from the
    joint prior. This is the regime the continuous back-end exists for."""
    from wolves.forecast import StrengthPerturbation

    n_teams = len(forecaster.fmt.teams)
    per_driver = gauss_hermite_worlds(mean=prior.mean, sd=prior.sd, nodes=nodes)
    lattice_worlds = nodes ** len(teams)

    rng = np.random.default_rng(seed)
    nodes_idx = _capped_lattice(len(teams), nodes, lattice_cap, rng)
    discrete = np.zeros(n_teams)
    total = 0.0
    for i, combo in enumerate(nodes_idx):
        weight = float(np.prod([per_driver[k].weight for k in combo]))
        perts = tuple(
            StrengthPerturbation(team=t, delta=per_driver[k].delta, reason="elicitation")
            for t, k in zip(teams, combo, strict=True)
            if per_driver[k].delta != 0.0
        )
        result = forecaster.simulate(n_sims=n_sims, seed=seed + i, perturbations=perts, parameter_uncertainty=False)
        discrete += weight * _title_vector(result, n_teams)
        total += weight
    discrete /= total

    latents = tuple(LatentEffect(reason="elicitation", targets={t: 1.0}, prior=prior) for t in teams)
    continuous = _title_vector(
        forecaster.simulate(n_sims=n_sims, seed=seed, latent_effects=latents, parameter_uncertainty=False),
        n_teams,
    )

    truths = prior.sample(rng, (n_truth, len(teams)))
    champions = []
    for i, draw in enumerate(truths):
        perts = tuple(
            StrengthPerturbation(team=t, delta=float(d), reason="elicitation")
            for t, d in zip(teams, draw, strict=True)
        )
        vec = _title_vector(
            forecaster.simulate(n_sims=n_sims, seed=seed + 2000 + i, perturbations=perts, parameter_uncertainty=False),
            n_teams,
        )
        champions.append(rng.choice(n_teams, p=vec))
    truth_dist = np.bincount(champions, minlength=n_teams).astype(np.float64) / n_truth

    return MultiDriverResult(
        n_drivers=len(teams),
        nodes_each=nodes,
        lattice_worlds=lattice_worlds,
        capped_worlds=len(nodes_idx),
        discrete_log_loss=_cross_entropy(truth_dist, discrete),
        continuous_log_loss=_cross_entropy(truth_dist, continuous),
    )


def _capped_lattice(drivers: int, nodes: int, cap: int, rng: np.random.Generator) -> list[tuple[int, ...]]:
    """The full node-index lattice, or a random subsample of it once it exceeds
    the cap (the honest fate of a many-driver discrete mixture)."""
    from itertools import product

    full = list(product(range(nodes), repeat=drivers))
    if len(full) <= cap:
        return full
    keep = rng.choice(len(full), size=cap, replace=False)
    return [full[i] for i in keep]


def _cross_entropy(truth: np.ndarray, forecast: np.ndarray) -> float:
    mask = truth > 0.0
    return float(-(truth[mask] * np.log(np.clip(forecast[mask], 1e-9, None))).sum())


def _entropy(dist: np.ndarray) -> float:
    mask = dist > 0.0
    return float(-(dist[mask] * np.log(dist[mask])).sum())
