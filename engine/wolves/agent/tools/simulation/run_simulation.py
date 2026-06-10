from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.forecast import Perturbation


class RunSimulationArgs(BaseModel):
    perturbations: list[Perturbation] = Field(default_factory=list)
    n_sims: int | None = None
    seed: int = 0


async def _run_simulation(args: RunSimulationArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    fc = deps.forecaster
    assert fc is not None
    n_sims = args.n_sims or deps.settings.n_sims
    with deps.runtime.observe(
        kind="quant",
        actor=deps.actor,
        name="run_simulation",
        input={"perturbations": [p.model_dump(mode="json") for p in args.perturbations], "n_sims": n_sims},
    ) as rec:
        outputs = await asyncio.to_thread(
            lambda: fc.sim_outputs(n_sims=n_sims, seed=args.seed, perturbations=tuple(args.perturbations))
        )
        rec.set_output({"n_sims": outputs.n_sims, "reach_probs": outputs.focus.reach_probs})
        rec.note(
            summary=f"sim {n_sims} runs, {len(args.perturbations)} perturbation(s)",
            reach_probs=outputs.focus.reach_probs,
        )
    titles = {t.team_id: t.champion_prob for t in outputs.teams}
    top = dict(sorted(titles.items(), key=lambda kv: kv[1], reverse=True)[:12])
    return ToolResult(
        payload={
            "title_probs": top,
            "focus": outputs.focus.reach_probs,
            "n_sims": outputs.n_sims,
            "seed": args.seed,
        }
    )


SPEC = ToolSpec(
    name="run_simulation",
    description=(
        "Run the full tournament simulation under typed perturbations (strength, tempo, home "
        "advantage, per-match rates or outcomes; deltas may carry Normal(mean, sd) magnitude "
        "uncertainty) and return the top title probabilities and the focus team's reach. Common random "
        "numbers by seed, so same-seed runs difference cleanly. For multi-world mixtures use "
        "wq.scenario_mixture in run_python, which also persists a submit-ready artifact."
    ),
    args_model=RunSimulationArgs,
    fn=_run_simulation,
)
