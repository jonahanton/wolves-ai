"""Mixture spread at exploration fidelity: the band a set of worlds implies.

Shared by the quant workbench (wq.mixture_spread) and the forecast node's
quick-look tool; the publish-time computation in publish_distributions.py is
the authoritative one, this is the cheap mirror the agent reads first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import numpy as np

from wolves.sim.distributions import STAGES, shrink_draws, weighted_quantiles

if TYPE_CHECKING:
    from wolves.forecast import Perturbation
    from wolves.sim.format import FormatData
    from wolves.sim.mc import SimResult

EXPLORATION_N_SIMS = 20_000
SPREAD_PARAMETER_DRAWS = 200
TOP_TEAMS = 8
CHAMPION = STAGES.index("champion")


class SpreadForecaster(Protocol):
    fmt: FormatData

    def simulate(
        self,
        *,
        n_sims: int = ...,
        seed: int = ...,
        perturbations: tuple[Perturbation, ...] = ...,
    ) -> SimResult: ...


@dataclass(frozen=True)
class SpreadRow:
    team: str
    mean: float
    p10: float
    p90: float
    width_pp: float
    floor_p10: float
    floor_p90: float
    floor_width_pp: float
    vs_floor: float
    yesterday_p10: float | None
    yesterday_p90: float | None
    world_means: dict[str, float]


@dataclass(frozen=True)
class SpreadResult:
    rows: list[SpreadRow]
    provenance: str
    n_worlds: int
    n_sims_per_world: int
    parameter_draws: int
    note: str


def _champion_draws(forecaster: SpreadForecaster, perturbations: list, *, n_sims: int, seed: int) -> np.ndarray:
    from wolves.sim.distributions import reach_by_draw

    result = forecaster.simulate(n_sims=n_sims, seed=seed, perturbations=tuple(perturbations))
    return reach_by_draw(forecaster.fmt, result, parameter_draws=SPREAD_PARAMETER_DRAWS)[:, CHAMPION, :]


def mixture_spread_rows(
    forecaster: SpreadForecaster,
    worlds: dict[str, tuple[float, list]],
    *,
    focus_team: str,
    teams: list[str] | None = None,
    yesterday_bands: dict[str, tuple[float, float]] | None = None,
    n_sims: int = EXPLORATION_N_SIMS,
    seed: int = 0,
) -> SpreadResult:
    """Compute the spread table for a set of (weight, perturbations) worlds."""
    fmt = forecaster.fmt
    team_ids = [t.id for t in fmt.teams]
    weights = {name: weight for name, (weight, _) in worlds.items()}
    sims_per_draw = max(n_sims // SPREAD_PARAMETER_DRAWS, 1)

    per_world = {
        name: shrink_draws(
            _champion_draws(forecaster, perturbations, n_sims=n_sims, seed=seed), sims_per_draw=sims_per_draw
        )
        for name, (_, perturbations) in worlds.items()
    }
    floor = shrink_draws(_champion_draws(forecaster, [], n_sims=n_sims, seed=seed), sims_per_draw=sims_per_draw)

    means = {
        team: float(sum(weights[name] * per_world[name][i].mean() for name in weights))
        for i, team in enumerate(team_ids)
    }
    if teams is None:
        ranked = sorted(team_ids, key=lambda t: means[t], reverse=True)
        teams = list(dict.fromkeys([focus_team, *ranked[:TOP_TEAMS]])) if focus_team in means else ranked[:TOP_TEAMS]

    rows: list[SpreadRow] = []
    for team in teams:
        i = team_ids.index(team)
        pooled = np.concatenate([per_world[name][i] for name in weights])
        pooled_weights = np.concatenate(
            [np.full(per_world[name][i].shape, weights[name] / per_world[name][i].size) for name in weights]
        )
        p10, p90 = weighted_quantiles(pooled, pooled_weights, (0.1, 0.9))
        floor_p10, floor_p90 = float(np.quantile(floor[i], 0.1)), float(np.quantile(floor[i], 0.9))
        width = (p90 - p10) * 100
        floor_width = (floor_p90 - floor_p10) * 100
        yesterday = (yesterday_bands or {}).get(team)
        rows.append(
            SpreadRow(
                team=team,
                mean=round(means[team], 4),
                p10=round(p10, 4),
                p90=round(p90, 4),
                width_pp=round(width, 1),
                floor_p10=round(floor_p10, 4),
                floor_p90=round(floor_p90, 4),
                floor_width_pp=round(floor_width, 1),
                vs_floor=round(width / floor_width, 2) if floor_width > 0 else float("inf"),
                yesterday_p10=yesterday[0] if yesterday else None,
                yesterday_p90=yesterday[1] if yesterday else None,
                world_means={name: round(float(per_world[name][i].mean()), 4) for name in weights},
            )
        )

    provenance = "worlds_and_parameters" if len(worlds) > 1 else "parameters_only"
    return SpreadResult(
        rows=rows,
        provenance=provenance,
        n_worlds=len(worlds),
        n_sims_per_world=n_sims,
        parameter_draws=SPREAD_PARAMETER_DRAWS,
        note=_note(rows, focus_team),
    )


def _note(rows: list[SpreadRow], focus_team: str) -> str:
    row = next((r for r in rows if r.team == focus_team), rows[0] if rows else None)
    if row is None:
        return "no teams in view"
    sentence = f"{row.team} band {row.width_pp}pp is {row.vs_floor}x the parameter floor"
    if row.yesterday_p10 is not None and row.yesterday_p90 is not None:
        overlaps = row.p10 <= row.yesterday_p90 and row.yesterday_p10 <= row.p90
        relation = "overlaps" if overlaps else "has moved off"
        sentence += (
            f" and {relation} yesterday's {round(row.yesterday_p10 * 100, 1)} to {round(row.yesterday_p90 * 100, 1)}"
        )
    return sentence


def yesterday_bands(snapshot_dir, *, before: str) -> dict[str, tuple[float, float]]:
    """Champion q10-q90 per team from the latest snapshot before the date; empty when absent."""
    from datetime import date

    from wolves.insights.what_changed import load_latest_snapshot

    previous = load_latest_snapshot(snapshot_dir, before=date.fromisoformat(before))
    if previous is None or previous.distributions is None:
        return {}
    block = previous.distributions
    if 0.1 not in block.quantile_levels or 0.9 not in block.quantile_levels:
        return {}
    q10_i, q90_i = block.quantile_levels.index(0.1), block.quantile_levels.index(0.9)
    out: dict[str, tuple[float, float]] = {}
    for team, dist in block.teams.items():
        quantiles = dist.quantiles.get("champion")
        if quantiles:
            out[team] = (quantiles[q10_i], quantiles[q90_i])
    return out
