from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.forecast import Perturbation
from wolves.insights.scenario import run_scenario
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class RunScenarioArgs(BaseModel):
    perturbations: list[Perturbation] = Field(min_length=1)
    n_sims: int = 20_000
    seed: int = 0


async def _run_scenario(args: RunScenarioArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    result = run_scenario(deps.forecaster, tuple(args.perturbations), n_sims=args.n_sims, seed=args.seed)
    return ToolResult(payload=result.model_dump(mode="json"))


SPEC = ToolSpec(
    name="run_scenario",
    description=(
        "Simulate a what-if world (one or more typed perturbations) against the baseline with "
        "common random numbers and return the title and per-round movers beyond 0.2pp. The cheap "
        "way to size a story before weighting it."
    ),
    args_model=RunScenarioArgs,
    fn=_run_scenario,
)
