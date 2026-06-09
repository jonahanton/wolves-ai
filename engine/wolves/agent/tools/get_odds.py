from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.clients.odds.markets import event_consensus
from wolves.tools._timeout import run_with_timeout


class GetOddsArgs(BaseModel):
    market: Literal["outrights", "h2h"] = "outrights"


async def _get_odds(args: GetOddsArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    deps.runtime.charge_data_fetch()
    with deps.runtime.observe(kind="data_fetch", actor=deps.actor, name=f"get_odds:{args.market}") as rec:
        call = deps.odds.outrights() if args.market == "outrights" else deps.odds.h2h()
        response = await run_with_timeout(
            call,
            tool_name="get_odds",
            timeout_seconds=deps.settings.tool_timeout_seconds,
        )
        events = [
            {
                "home": event.home_team,
                "away": event.away_team,
                "commence_time": event.commence_time.isoformat() if event.commence_time else None,
                "consensus": {name: round(p, 4) for name, p in event_consensus(event, market_key=args.market).items()},
            }
            for event in response.events
        ]
        rec.set_output({"events": len(events)})
        rec.note(
            summary=f"odds {args.market}: {len(events)} event(s), {response.credits.remaining} credits left",
            market=args.market,
            credits_remaining=response.credits.remaining,
        )
    return ToolResult(
        payload={
            "market": args.market,
            "events": events,
            "credits_remaining": response.credits.remaining,
        }
    )


SPEC = ToolSpec(
    name="get_odds",
    description=(
        "De-vigged bookmaker consensus probabilities (power-method de-vig, log-odds averaging across books). "
        "'outrights' gives tournament winner probabilities, 'h2h' gives match win/draw/loss. "
        "This is your calibration anchor: always state the market number before diverging from it."
    ),
    args_model=GetOddsArgs,
    fn=_get_odds,
)
