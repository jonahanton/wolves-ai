"""wq.mixture_spread: read the band a mixture's worlds imply before registering it."""

from __future__ import annotations

from typing import Any

from wolves.quant.wolves_quant._mixture import Factor, Scenario, _factor_blocks, _worlds
from wolves.quant.wolves_quant._state import SESSION, context, forecaster
from wolves.sim.spread import EXPLORATION_N_SIMS, mixture_spread_rows, yesterday_bands


def mixture_spread(
    scenarios: list[Scenario | dict[str, Any]] | None = None,
    *,
    factors: list[Factor | dict[str, Any]] | None = None,
    artifact: str | None = None,
    teams: list[str] | None = None,
    n_sims: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """The band the mixture's worlds imply, against the parameter-noise floor.

    Pass exactly one of scenarios, factors or artifact (a registered mixture
    id). Returns teams (a DataFrame: mean, p10, p90, width_pp, floor columns,
    vs_floor, yesterday band, one mean column per world), provenance, n_worlds,
    n_sims_per_world, parameter_draws and a one-sentence note for the focus
    team. vs_floor near 1 over contested evidence means a believed branch is
    missing; comfortably above means the width is earned."""
    import pandas as pd

    worlds = _resolve_worlds(scenarios, factors, artifact)
    ctx = context()
    n = n_sims or EXPLORATION_N_SIMS
    key = (artifact or "inline", tuple(sorted(worlds)), tuple(teams or ()), n, seed)
    cached = _CACHE.get(key)
    if cached is None:
        SESSION.usage.sims += len(worlds) + 1
        cached = mixture_spread_rows(
            forecaster(),
            worlds,
            focus_team=ctx.focus_team,
            teams=teams,
            yesterday_bands=yesterday_bands(_snapshot_dir(), before=ctx.as_of),
            n_sims=n,
            seed=seed,
        )
        _CACHE[key] = cached
    frame = pd.DataFrame(
        [
            {
                "mean": r.mean,
                "p10": r.p10,
                "p90": r.p90,
                "width_pp": r.width_pp,
                "floor_p10": r.floor_p10,
                "floor_p90": r.floor_p90,
                "floor_width_pp": r.floor_width_pp,
                "vs_floor": r.vs_floor,
                "yesterday_p10": r.yesterday_p10,
                "yesterday_p90": r.yesterday_p90,
                **r.world_means,
            }
            for r in cached.rows
        ],
        index=[r.team for r in cached.rows],
    )
    return {
        "teams": frame,
        "provenance": cached.provenance,
        "n_worlds": cached.n_worlds,
        "n_sims_per_world": cached.n_sims_per_world,
        "parameter_draws": cached.parameter_draws,
        "note": cached.note,
    }


_CACHE: dict[tuple, Any] = {}


def _snapshot_dir():
    from pathlib import Path

    return Path(context().runs_root) / "snapshots"


def _resolve_worlds(
    scenarios: list[Scenario | dict[str, Any]] | None,
    factors: list[Factor | dict[str, Any]] | None,
    artifact_id: str | None,
) -> dict[str, tuple[float, list]]:
    if sum(x is not None for x in (scenarios, factors, artifact_id)) != 1:
        raise ValueError("pass exactly one of scenarios, factors or artifact")
    if artifact_id is not None:
        from pydantic import TypeAdapter

        from wolves.forecast import Perturbation
        from wolves.quant.wolves_quant._data import artifact as load_artifact

        adapter = TypeAdapter[Perturbation](Perturbation)
        payload = load_artifact(artifact_id)
        weights: dict[str, float] = payload.get("weights") or {}
        worlds_block: dict[str, dict] = payload.get("worlds") or {}
        if not weights or not worlds_block:
            raise ValueError(f"artifact {artifact_id!r} carries no worlds block")
        return {
            name: (weight, [adapter.validate_python(p) for p in worlds_block[name].get("perturbations", [])])
            for name, weight in weights.items()
        }
    blocks = _factor_blocks(scenarios, factors)
    lattice = _worlds(blocks, None)
    return {key: (weight, [p for s in parts for p in s.perturbations]) for key, weight, parts in lattice}
