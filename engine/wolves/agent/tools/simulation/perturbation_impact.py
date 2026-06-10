from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.forecast import Perturbation


class PerturbationImpactArgs(BaseModel):
    perturbation: Perturbation
    n_sims: int = 20_000
    seed: int = 0


async def _perturbation_impact(args: PerturbationImpactArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    fc = deps.forecaster
    assert fc is not None
    deltas = fc.perturbation_impact(args.perturbation, n_sims=args.n_sims, seed=args.seed)
    a = fc.title_probs(n_sims=args.n_sims, seed=args.seed)
    b = fc.title_probs(n_sims=args.n_sims, seed=args.seed + 1)
    floor = round(max(abs(a[t] - b.get(t, 0.0)) for t in a) * 100, 3)
    movers = dict(sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10])
    return ToolResult(payload={"deltas_pp": movers, "noise_floor_pp": floor})


SPEC = ToolSpec(
    name="perturbation_impact",
    description=(
        "Per-team pp title-probability deltas for one typed perturbation, common random numbers, "
        "with the paired-seed noise floor attached: any cross-team delta below the floor is "
        "simulation noise, not signal."
    ),
    args_model=PerturbationImpactArgs,
    fn=_perturbation_impact,
)
