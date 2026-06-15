from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.agent.tools.retrieval.get_odds import _outrights_payload
from wolves.insights.market_gaps import market_gaps
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult

logger = logging.getLogger(__name__)


class MarketGapsArgs(BaseModel):
    n_sims: int = 20_000
    seed: int = 0


async def _current_outrights(deps: AgentDeps) -> dict[str, Any] | None:
    if cached := deps.market_cache.get("outrights"):
        return cached
    try:
        deps.runtime.charge_data_fetch()
        with deps.runtime.observe(kind="data_fetch", actor=deps.actor, name="market_gaps:outrights") as rec:
            payload = await run_with_timeout(
                _outrights_payload(deps),
                tool_name="market_gaps",
                timeout_seconds=deps.settings.tool_timeout_seconds,
            )
            deps.market_cache["outrights"] = payload
            rec.set_output({"market": "outrights"})
            rec.note(
                summary=f"odds outrights for market gaps: {payload['credits_remaining']} credits left",
                market="outrights",
                credits_remaining=payload["credits_remaining"],
            )
            return payload
    except Exception as exc:
        logger.warning("market_gaps live odds fetch failed; falling back to archive: %s", exc)
        return None


async def _market_gaps(args: MarketGapsArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    current = await _current_outrights(deps)
    current_legs = current.get("legs", {}) if current is not None else {}
    table = market_gaps(
        deps.forecaster,
        deps.settings.runs_root / "odds-archive",
        current_market=current.get("consensus") if current is not None else None,
        current_polymarket=current_legs.get("polymarket"),
        current_as_of=current.get("fetched_at") if current is not None else None,
        current_prices_updated_oldest=current.get("prices_updated_oldest") if current is not None else None,
        current_prices_updated_newest=current.get("prices_updated_newest") if current is not None else None,
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
        "other is itself a signal. prices_updated_oldest/newest say when the bookmaker prices were "
        "last refreshed, so check them before treating a gap as news the market has not seen. Each "
        "gap is a research question: what does the market believe that the model does not, or vice versa?"
    ),
    args_model=MarketGapsArgs,
    fn=_market_gaps,
)
