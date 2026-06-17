from __future__ import annotations

from dataclasses import asdict
from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class MixtureSpreadArgs(BaseModel):
    artifact_id: str
    teams: list[str] | None = None


def spread_for_artifact(deps: AgentDeps, artifact_id: str, *, teams: list[str] | None = None) -> dict[str, Any] | None:
    """Spread rows for a registered mixture artifact; None when it cannot price."""
    from wolves.agent.forecast_artifact import ForecastArtifactError, worlds_from_payload
    from wolves.sim.spread import mixture_spread_rows, yesterday_bands

    if deps.forecaster is None or deps.artifacts is None:
        return None
    artifact = deps.artifacts.get(artifact_id)
    if artifact is None:
        return None
    try:
        worlds = worlds_from_payload(artifact.payload)
    except ForecastArtifactError:
        return None
    bands = yesterday_bands(deps.settings.runs_root / "snapshots", before=deps.as_of) if deps.as_of else {}
    result = mixture_spread_rows(
        deps.forecaster,
        {w.name: (w.weight, list(w.perturbations)) for w in worlds},
        focus_team=deps.settings.focus_team,
        teams=teams,
        yesterday_bands=bands,
    )
    return {
        "teams": [asdict(row) for row in result.rows],
        "provenance": result.provenance,
        "n_worlds": result.n_worlds,
        "n_sims_per_world": result.n_sims_per_world,
        "parameter_draws": result.parameter_draws,
        "note": result.note,
    }


async def _mixture_spread(args: MixtureSpreadArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    payload = spread_for_artifact(deps, args.artifact_id, teams=args.teams)
    if payload is None:
        return ToolResult(payload={"error": f"artifact {args.artifact_id!r} is unknown or carries no worlds"})
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="mixture_spread",
    description=(
        "The band a registered mixture's worlds imply, per team, against the model's parameter-noise "
        "floor and yesterday's published band. Read vs_floor before drafting: near 1 over contested "
        "evidence means a believed branch is missing; comfortably above means the width is earned. "
        "No draft submission needed."
    ),
    args_model=MixtureSpreadArgs,
    fn=_mixture_spread,
)
