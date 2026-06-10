from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.insights.explain import model_explain


class ModelExplainArgs(BaseModel):
    team: str


async def _model_explain(args: ModelExplainArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    explanation = model_explain(deps.forecaster, args.team)
    return ToolResult(payload=explanation.model_dump(mode="json"))


SPEC = ToolSpec(
    name="model_explain",
    description=(
        "Why the model rates a team where it does: fitted strength decomposed into the weighted "
        "results pulling it up and down, Elo trajectory and squad value. Free to call."
    ),
    args_model=ModelExplainArgs,
    fn=_model_explain,
)
