"""Assemble the snapshot distributions block and its sidecar in one pass.

Publish coherence order per open cell: shrink per-world draws, settle or map
through the same governor blend as the headline, widen when the dispersion
governor demands it, floor against the anchor's parameter-noise band, then
summarise. The floor reference is the deterministic anchor world; runs with
a single world skip the floor because it would be a no-op against itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from wolves.sidecars import CellShape, DistributionsSidecar
from wolves.sim.distributions import STAGES, apply_blend, cell_distribution, reach_by_draw
from wolves.snapshot import DistributionsBlock, TeamDistributions

if TYPE_CHECKING:
    from wolves.agent.stream import StreamRecord
    from wolves.config import Settings
    from wolves.sim.format import FormatData
    from wolves.sim.mc import SimResult

SIDECAR_NAME = "distributions"


def build_run_distributions(
    fmt: FormatData,
    per_world_results: dict[str, SimResult],
    weights: dict[str, float],
    *,
    settings: Settings,
    played: frozenset[int],
    rng_seed: int,
    anchor_result: SimResult | None = None,
    effective_d: float = 1.0,
    stream_records: list[StreamRecord] | None = None,
) -> tuple[DistributionsBlock, dict[str, object]]:
    """Build the snapshot block plus every sidecar payload for one run."""
    from wolves.sidecars import SIDECARS, SidecarInputs
    from wolves.sim.model_engine import PARAMETER_DRAWS

    block, dist_sidecar = build_distributions(
        fmt,
        per_world_results,
        weights,
        parameter_draws=PARAMETER_DRAWS,
        settings=settings,
        anchor_result=anchor_result,
        effective_d=effective_d,
        stream_records=stream_records,
    )
    inputs = SidecarInputs(
        fmt=fmt,
        per_world_results=per_world_results,
        weights=weights,
        parameter_draws=PARAMETER_DRAWS,
        rng_seed=rng_seed,
        played=played,
    )
    sidecars: dict[str, object] = {SIDECAR_NAME: dist_sidecar}
    for spec in SIDECARS:
        if spec.produce is not None:
            sidecars[spec.name] = spec.produce(inputs)
    return block, sidecars


def widen_about_mean(samples: np.ndarray, factor: float) -> np.ndarray:
    """Scale logit offsets about the mean; the dispersion governor's widening."""
    from wolves.sim.distributions import _logit, _sigmoid

    centre = _logit(float(samples.mean()))
    return _sigmoid(centre + factor * (_logit(samples) - centre))


def build_distributions(
    fmt: FormatData,
    per_world_results: dict[str, SimResult],
    weights: dict[str, float],
    *,
    parameter_draws: int,
    settings: Settings,
    anchor_result: SimResult | None = None,
    effective_d: float = 1.0,
    stream_records: list[StreamRecord] | None = None,
) -> tuple[DistributionsBlock, DistributionsSidecar]:
    """Build the quantile block and the histogram sidecar from per-world results."""
    from wolves.agent.stream import dispersion_scale

    levels = tuple(settings.distribution_quantiles)
    n_bins = settings.distribution_bins
    per_world_reach = {
        name: reach_by_draw(fmt, result, parameter_draws=parameter_draws) for name, result in per_world_results.items()
    }
    n_sims = next(iter(per_world_results.values())).n_sims
    sims_per_draw = n_sims // parameter_draws
    anchor_reach = (
        reach_by_draw(fmt, anchor_result, parameter_draws=parameter_draws) if anchor_result is not None else None
    )
    governed = effective_d < 1.0
    dispersion = dispersion_scale(stream_records or [], min_n=settings.dispersion_governor_min_n)
    provenance = "worlds_and_parameters" if len(weights) > 1 else "parameters_only"

    teams: dict[str, TeamDistributions] = {}
    shapes: dict[str, dict[str, CellShape]] = {}
    any_floored = False
    for i, team in enumerate(fmt.teams):
        quantiles: dict[str, list[float]] = {}
        settled: dict[str, int] = {}
        team_shapes: dict[str, CellShape] = {}
        for s, stage in enumerate(STAGES):
            per_world_draws = {name: per_world_reach[name][i, s, :] for name in weights}
            anchor_cell = anchor_reach[i, s, :] if anchor_reach is not None else None
            anchor_mean = float(anchor_cell.mean()) if anchor_cell is not None else None
            blend = None
            if governed and anchor_mean is not None and 0.0 < anchor_mean < 1.0:
                blend = (anchor_mean, effective_d)
            floor = None
            if settings.dispersion_floor_enabled and anchor_cell is not None and len(weights) > 1:
                floor = anchor_cell
            cell = cell_distribution(
                per_world_draws,
                weights,
                sims_per_draw=sims_per_draw,
                quantile_levels=levels,
                n_bins=n_bins,
                blend=blend,
                floor_samples=floor,
            )
            if cell.settled is not None:
                settled[stage] = cell.settled
                continue
            if dispersion > 1.0:
                cell = _widened_cell(
                    per_world_draws,
                    weights,
                    sims_per_draw=sims_per_draw,
                    levels=levels,
                    n_bins=n_bins,
                    blend=blend,
                    floor=floor,
                    factor=dispersion,
                )
            quantiles[stage] = cell.quantiles or []
            any_floored = any_floored or cell.width_floored
            team_shapes[stage] = CellShape(
                bin_edges=cell.bin_edges or [],
                histogram=cell.histogram or [],
                world_bins=cell.world_bins or {},
                components={
                    name: {"weight": c.weight, "mean": c.mean, "sd": c.sd}
                    for name, c in (cell.components or {}).items()
                },
            )
        teams[team.id] = TeamDistributions(quantiles=quantiles, settled=settled)
        if team_shapes:
            shapes[team.id] = team_shapes

    block = DistributionsBlock(
        quantile_levels=list(levels),
        provenance=provenance,
        n_worlds=len(weights),
        width_floored=any_floored,
        sidecar=SIDECAR_NAME,
        teams=teams,
    )
    sidecar = DistributionsSidecar(quantile_levels=list(levels), provenance=provenance, teams=shapes)
    return block, sidecar


def _widened_cell(
    per_world_draws: dict[str, np.ndarray],
    weights: dict[str, float],
    *,
    sims_per_draw: int,
    levels: tuple[float, ...],
    n_bins: int,
    blend: tuple[float, float] | None,
    floor: np.ndarray | None,
    factor: float,
):
    """Re-run the cell with dispersion-governor widening applied per world.

    Widening each world about its own mean preserves the per-world component
    story; the mixture mean moves only by the Jensen drift, which the stream
    score then measures against."""
    from wolves.sim.distributions import shrink_draws

    widened = {
        name: widen_about_mean(shrink_draws(np.asarray(draws, dtype=np.float64), sims_per_draw=sims_per_draw), factor)
        for name, draws in per_world_draws.items()
    }
    blended_floor = floor
    if blend is not None and floor is not None:
        anchor, d = blend
        blended_floor = apply_blend(np.asarray(floor, dtype=np.float64), anchor=anchor, d=d)
    if blend is not None:
        anchor, d = blend
        widened = {name: apply_blend(draws, anchor=anchor, d=d) for name, draws in widened.items()}
    # sims_per_draw is huge so the second shrink inside cell_distribution is a
    # near no-op on already-shrunk samples; pass the widened draws straight through.
    return cell_distribution(
        widened,
        weights,
        sims_per_draw=10**9,
        quantile_levels=levels,
        n_bins=n_bins,
        blend=None,
        floor_samples=blended_floor,
    )
