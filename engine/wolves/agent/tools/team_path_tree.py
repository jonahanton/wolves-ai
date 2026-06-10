from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.insights.path_tree import team_path_tree


class TeamPathTreeArgs(BaseModel):
    team: str
    view: Literal["reach", "title"] = "reach"
    n_sims: int = 20_000
    seed: int = 0


async def _team_path_tree(args: TeamPathTreeArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    tree = team_path_tree(deps.forecaster, args.team, view=args.view, n_sims=args.n_sims, seed=args.seed)
    return ToolResult(payload=tree.model_dump(mode="json"))


SPEC = ToolSpec(
    name="team_path_tree",
    description=(
        "One team's route through the bracket: qualification split, per-stage advance "
        "probabilities and likely opponents per slot. view='title' conditions on winning it all."
    ),
    args_model=TeamPathTreeArgs,
    fn=_team_path_tree,
)
