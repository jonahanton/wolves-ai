from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.insights.model_vs_market import model_vs_market


class ModelVsMarketArgs(BaseModel):
    n_sims: int = 20_000
    seed: int = 0


async def _model_vs_market(args: ModelVsMarketArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    table = model_vs_market(
        deps.forecaster,
        deps.settings.runs_root / "odds-archive",
        n_sims=args.n_sims,
        seed=args.seed,
    )
    return ToolResult(payload=table.model_dump(mode="json"))


SPEC = ToolSpec(
    name="model_vs_market",
    description=(
        "The daily gap table: model vs market vs blend title probabilities per team, largest gaps "
        "first. Each gap is a research question: what does the market believe that the model "
        "does not, or vice versa?"
    ),
    args_model=ModelVsMarketArgs,
    fn=_model_vs_market,
)
