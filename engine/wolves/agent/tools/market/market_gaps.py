from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.insights.market_gaps import market_gaps
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class MarketGapsArgs(BaseModel):
    n_sims: int = 20_000
    seed: int = 0


async def _market_gaps(args: MarketGapsArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    table = market_gaps(
        deps.forecaster,
        deps.settings.runs_root / "odds-archive",
        n_sims=args.n_sims,
        seed=args.seed,
    )
    return ToolResult(payload=table.model_dump(mode="json"))


SPEC = ToolSpec(
    name="market_gaps",
    description=(
        "The daily gap table: model vs bookmaker consensus vs Polymarket title probabilities per "
        "team, largest gaps first. A null gap means no price exists for that team, not agreement. "
        "legs_disagree_pp is bookmakers minus Polymarket: the two market legs arguing with each "
        "other is itself a signal. Each gap is a research question: what does the market believe "
        "that the model does not, or vice versa?"
    ),
    args_model=MarketGapsArgs,
    fn=_market_gaps,
)
