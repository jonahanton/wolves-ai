from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult


class RunSimulationArgs(BaseModel):
    rating_overrides: dict[str, float] = Field(
        default_factory=dict, description="team_id to Elo delta, e.g. {'england': 15.0}"
    )
    fixture_goal_offsets: dict[str, list[float]] = Field(
        default_factory=dict, description="match number to [home_goals, away_goals] expected-goal offsets"
    )
    n_sims: int | None = None
    seed: int | None = None


async def _run_simulation(args: RunSimulationArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    try:
        offsets = {int(match): (values[0], values[1]) for match, values in args.fixture_goal_offsets.items()}
    except (ValueError, IndexError):
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="invalid_arguments",
                message="fixture_goal_offsets must map match numbers to [home, away] pairs",
            ),
        )
    n_sims = args.n_sims or deps.settings.n_sims
    with deps.runtime.observe(
        kind="quant",
        actor=deps.actor,
        name="run_simulation",
        input={"rating_overrides": args.rating_overrides, "n_sims": n_sims},
    ) as rec:
        outputs = await asyncio.to_thread(
            deps.sim.run_simulation,
            args.rating_overrides,
            offsets,
            n_sims,
            args.seed,
        )
        rec.set_output({"n_sims": outputs.n_sims, "reach_probs": outputs.england.reach_probs})
        rec.note(
            summary=f"sim {n_sims} runs, {len(args.rating_overrides)} override(s)",
            reach_probs=outputs.england.reach_probs,
        )
    return ToolResult(payload=outputs.model_dump(mode="json"))


SPEC = ToolSpec(
    name="run_simulation",
    description=(
        "Run the Monte Carlo tournament simulation with your chosen rating overrides (Elo deltas per team) "
        "and per-fixture expected-goal offsets. Returns England finish/reach probabilities, conditional paths "
        "and all knockout slot candidate distributions. Run it as often as budget allows; reason with it."
    ),
    args_model=RunSimulationArgs,
    fn=_run_simulation,
)
