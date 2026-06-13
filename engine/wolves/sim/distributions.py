"""Epistemic distributions over reach probabilities, per team per stage.

Pure maths over a SimResult: per-draw reach fractions, method-of-moments
shrinkage that removes Monte Carlo noise, weighted mixture quantiles with
per-world histogram components, the governor blend, a width floor that only
widens, and the settled-cell rule that publishes facts as flags rather than
degenerate distributions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wolves.sim.format import FormatData
from wolves.sim.mc import SimResult

STAGES: tuple[str, ...] = ("r32", "r16", "qf", "sf", "final", "champion")

_LOGIT_CLIP = 1e-9


def reach_by_draw(fmt: FormatData, result: SimResult, *, parameter_draws: int) -> np.ndarray:
    """Per-draw reach fractions, shape (teams, stages, min(draws, n_sims)), stages per STAGES."""
    n_sims = result.n_sims
    n_teams = len(fmt.teams)
    reached = {stage: np.zeros((n_teams, n_sims), dtype=np.float64) for stage in STAGES}
    sims = np.arange(n_sims)
    next_round = {"r32": "r16", "r16": "qf", "qf": "sf", "sf": "final"}
    final = max(m.match for m in fmt.knockout if m.stage == "final")
    for m in fmt.knockout:
        if m.stage == "r32":
            reached["r32"][result.ko_home[m.match], sims] = 1.0
            reached["r32"][result.ko_away[m.match], sims] = 1.0
        if m.stage in next_round:
            reached[next_round[m.stage]][result.ko_winner[m.match], sims] = 1.0
    reached["champion"][result.ko_winner[final], sims] = 1.0
    # Sim i carries covariance draw i % parameter_draws (PoissonMatchEngine.begin);
    # fewer sims than draws leaves only the first n_sims draws populated.
    effective = min(parameter_draws, n_sims)
    draw_idx = sims % parameter_draws
    counts = np.bincount(draw_idx, minlength=effective).astype(np.float64)
    out = np.zeros((n_teams, len(STAGES), effective))
    for s, stage in enumerate(STAGES):
        indicators = reached[stage]
        for t in range(n_teams):
            out[t, s, :] = np.bincount(draw_idx, weights=indicators[t], minlength=effective) / counts
    return out


def shrink_draws(per_draw: np.ndarray, *, sims_per_draw: int) -> np.ndarray:
    """Shrink per-draw values towards their mean, removing binomial MC noise."""
    mean = per_draw.mean(axis=-1, keepdims=True)
    var_total = per_draw.var(axis=-1, keepdims=True)
    mc_var = (per_draw * (1.0 - per_draw)).mean(axis=-1, keepdims=True) / sims_per_draw
    var_epi = np.maximum(var_total - mc_var, 0.0)
    factor = np.divide(np.sqrt(var_epi), np.sqrt(var_total), out=np.zeros_like(var_total), where=var_total > 0)
    return mean + factor * (per_draw - mean)


@dataclass(frozen=True)
class WorldComponent:
    weight: float
    mean: float
    sd: float


@dataclass(frozen=True)
class MixtureDistribution:
    quantiles: list[float]
    bin_edges: list[float]
    histogram: list[float]
    world_bins: dict[str, list[float]]
    components: dict[str, WorldComponent]


def _pooled(per_world_draws: dict[str, np.ndarray], weights: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    samples = np.concatenate([np.asarray(per_world_draws[name], dtype=np.float64) for name in weights])
    sample_weights = np.concatenate(
        [np.full(len(per_world_draws[name]), weights[name] / len(per_world_draws[name])) for name in weights]
    )
    return samples, sample_weights


def weighted_quantiles(samples: np.ndarray, sample_weights: np.ndarray, levels: tuple[float, ...]) -> list[float]:
    """Interpolated weighted quantiles over (sample, weight) pairs."""
    order = np.argsort(samples)
    sorted_samples = samples[order]
    cumulative = np.cumsum(sample_weights[order])
    cumulative /= cumulative[-1]
    return [float(np.interp(level, cumulative, sorted_samples)) for level in levels]


def _bin_edges(samples: np.ndarray, n_bins: int) -> np.ndarray:
    # Equal-width bins over the occupied range padded by one bin width and
    # clipped to [0, 1], so a tight cluster still renders with visible shape.
    lo, hi = float(samples.min()), float(samples.max())
    width = max((hi - lo) / n_bins, 1e-6)
    return np.linspace(max(lo - width, 0.0), min(hi + width, 1.0), n_bins + 1)


def mixture_distribution(
    per_world_draws: dict[str, np.ndarray],
    weights: dict[str, float],
    *,
    quantile_levels: tuple[float, ...],
    n_bins: int,
) -> MixtureDistribution:
    """Weighted quantiles, histogram and per-world components for one cell."""
    samples, sample_weights = _pooled(per_world_draws, weights)
    quantiles = weighted_quantiles(samples, sample_weights, quantile_levels)
    edges = _bin_edges(samples, n_bins)
    histogram = np.zeros(n_bins)
    world_bins: dict[str, list[float]] = {}
    components: dict[str, WorldComponent] = {}
    for name, weight in weights.items():
        draws = np.asarray(per_world_draws[name], dtype=np.float64)
        mass, _ = np.histogram(draws, bins=edges)
        contribution = weight * mass / len(draws)
        histogram += contribution
        world_bins[name] = [round(float(v), 6) for v in contribution]
        components[name] = WorldComponent(
            weight=weight, mean=round(float(draws.mean()), 6), sd=round(float(draws.std()), 6)
        )
    return MixtureDistribution(
        quantiles=[round(q, 6) for q in quantiles],
        bin_edges=[round(float(e), 6) for e in edges],
        histogram=[round(float(v), 6) for v in histogram],
        world_bins=world_bins,
        components=components,
    )


def _logit(p: np.ndarray | float) -> np.ndarray | float:
    clipped = np.clip(p, _LOGIT_CLIP, 1.0 - _LOGIT_CLIP)
    return np.log(clipped / (1.0 - clipped))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def apply_blend(samples: np.ndarray, *, anchor: float, d: float) -> np.ndarray:
    """Map samples through the governor blend in log-odds, as the headline is."""
    if anchor <= 0.0 or anchor >= 1.0:
        raise ValueError(f"blend anchor {anchor} is not an open probability; settled cells never blend")
    anchor_logit = _logit(anchor)
    return _sigmoid(anchor_logit + d * (_logit(samples) - anchor_logit))


def floor_width(samples: np.ndarray, floor_samples: np.ndarray) -> np.ndarray:
    """Widen samples about their mean until the q10-q90 width is at least the floor's."""
    q10, q90 = np.quantile(samples, (0.1, 0.9))
    floor_q10, floor_q90 = np.quantile(floor_samples, (0.1, 0.9))
    if q90 - q10 >= floor_q90 - floor_q10:
        return samples
    mean = float(samples.mean())
    centre = _logit(mean)
    offsets = _logit(samples) - centre

    def widen(factor: float) -> np.ndarray:
        return _recentre(_sigmoid(centre + factor * offsets), target_mean=mean)

    def width(factor: float) -> float:
        lo, hi = np.quantile(widen(factor), (0.1, 0.9))
        return float(hi - lo)

    target = float(floor_q90 - floor_q10)
    lo_f, hi_f = 1.0, 2.0
    # Recentred probability-space width is monotone in the logit-space factor;
    # grow the bracket, then bisect.
    while width(hi_f) < target and hi_f < 1e6:
        hi_f *= 2.0
    for _ in range(60):
        mid = (lo_f + hi_f) / 2.0
        if width(mid) < target:
            lo_f = mid
        else:
            hi_f = mid
    return widen(hi_f)


def _recentre(samples: np.ndarray, *, target_mean: float) -> np.ndarray:
    # Sigmoid convexity drifts the mean when widening; a logit-space shift
    # restores it so the floor never moves the headline.
    logits = _logit(samples)
    lo, hi = -1.0, 1.0
    while _sigmoid(logits + lo).mean() > target_mean and lo > -50:
        lo *= 2.0
    while _sigmoid(logits + hi).mean() < target_mean and hi < 50:
        hi *= 2.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if _sigmoid(logits + mid).mean() < target_mean:
            lo = mid
        else:
            hi = mid
    return _sigmoid(logits + (lo + hi) / 2.0)


def classify_settled(mean_p: float, *, eps: float = 1e-4) -> bool:
    """A cell is settled once its mean rounds to a fact at publish resolution."""
    return mean_p <= eps or mean_p >= 1.0 - eps


@dataclass(frozen=True)
class CellResult:
    settled: int | None = None
    quantiles: list[float] | None = None
    bin_edges: list[float] | None = None
    histogram: list[float] | None = None
    world_bins: dict[str, list[float]] | None = None
    components: dict[str, WorldComponent] | None = None
    width_floored: bool = False


def cell_distribution(
    per_world_draws: dict[str, np.ndarray],
    weights: dict[str, float],
    *,
    sims_per_draw: int,
    quantile_levels: tuple[float, ...],
    n_bins: int,
    blend: tuple[float, float] | None = None,
    floor_samples: np.ndarray | None = None,
    settled_eps: float = 1e-4,
) -> CellResult:
    """Run the publish pipeline for one cell: shrink, settle or blend, floor, summarise."""
    shrunk = {
        name: shrink_draws(np.asarray(draws, dtype=np.float64), sims_per_draw=sims_per_draw)
        for name, draws in per_world_draws.items()
    }
    mean_p = float(sum(weights[name] * shrunk[name].mean() for name in weights))
    if classify_settled(mean_p, eps=settled_eps):
        return CellResult(settled=int(mean_p >= 0.5))

    floored = False
    blended_floor = floor_samples
    if blend is not None:
        anchor, d = blend
        if d < 1.0:
            shrunk = {name: apply_blend(draws, anchor=anchor, d=d) for name, draws in shrunk.items()}
            if blended_floor is not None:
                # The floor is the anchor's own band, compared in published space.
                blended_floor = apply_blend(blended_floor, anchor=anchor, d=d)
    if blended_floor is not None:
        pooled, _ = _pooled(shrunk, weights)
        widened = floor_width(pooled, np.asarray(blended_floor, dtype=np.float64))
        if widened is not pooled:
            floored = True
            # The floor applies one monotone map to every pooled sample, so the
            # per-world structure survives a re-split by the original slicing.
            offsets = np.cumsum([0] + [len(shrunk[name]) for name in weights])
            shrunk = {name: widened[offsets[i] : offsets[i + 1]] for i, name in enumerate(weights)}
    mixture = mixture_distribution(shrunk, weights, quantile_levels=quantile_levels, n_bins=n_bins)
    return CellResult(
        quantiles=mixture.quantiles,
        bin_edges=mixture.bin_edges,
        histogram=mixture.histogram,
        world_bins=mixture.world_bins,
        components=mixture.components,
        width_floored=floored,
    )
