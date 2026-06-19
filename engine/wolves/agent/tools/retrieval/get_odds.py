from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.clients.odds import OddsEvent, event_consensus, market_last_updates, team_id_for_name, winner_probabilities
from wolves.markets.devig import weighted_consensus
from wolves.sim.format import Team, load_format
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.errors import ToolTimeoutError
from wolves.toolkit.result import ToolResult

logger = logging.getLogger(__name__)


class GetOddsArgs(BaseModel):
    market: Literal["outrights", "h2h"] = "outrights"


def _round4(probs: dict[str, float]) -> dict[str, float]:
    return {name: round(p, 4) for name, p in probs.items()}


def _freshness(events: list[OddsEvent], *, market_key: str) -> dict[str, str | None]:
    updates = [u for event in events for u in market_last_updates(event, market_key=market_key)]
    return {
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "prices_updated_oldest": min(updates).isoformat() if updates else None,
        "prices_updated_newest": max(updates).isoformat() if updates else None,
    }


def _bookmaker_leg(events: list[OddsEvent], teams: list[Team]) -> dict[str, float]:
    """De-vigged bookmaker consensus keyed by team id; unmapped outcomes dropped, renormalised."""
    mapped: dict[str, float] = {}
    for event in events:
        for name, prob in event_consensus(event, market_key="outrights").items():
            team_id = team_id_for_name(name, teams)
            if team_id is not None:
                mapped[team_id] = mapped.get(team_id, 0.0) + prob
    total = sum(mapped.values())
    if total <= 0.0:
        return {}
    return {team_id: p / total for team_id, p in mapped.items()}


type _BookmakerLeg = tuple[dict[str, float], int | None, dict[str, str | None], str | None]


async def _bookmaker_leg_or_degrade(deps: AgentDeps, teams: list[Team]) -> _BookmakerLeg:
    try:
        response = await run_with_timeout(
            deps.odds.outrights(),
            tool_name="get_odds",
            timeout_seconds=deps.settings.tool_timeout_seconds,
        )
    except (httpx.HTTPError, ToolTimeoutError) as exc:
        logger.warning("bookmaker odds unavailable, falling back to polymarket-only consensus: %s", exc)
        return {}, None, _freshness([], market_key="outrights"), str(exc)
    return (
        _bookmaker_leg(response.events, teams),
        response.credits.remaining,
        _freshness(response.events, market_key="outrights"),
        None,
    )


async def _outrights_payload(deps: AgentDeps) -> dict[str, Any]:
    teams = load_format(deps.settings.data_dir).teams
    bookmaker_leg, credits_remaining, freshness, bookmaker_error = await _bookmaker_leg_or_degrade(deps, teams)
    markets = await run_with_timeout(
        deps.polymarket.winner_markets(),
        tool_name="get_odds",
        timeout_seconds=deps.settings.tool_timeout_seconds,
    )
    legs = {
        "bookmakers": bookmaker_leg,
        "polymarket": winner_probabilities(markets, teams),
    }
    weights = {
        "bookmakers": deps.settings.bookmaker_leg_weight,
        "polymarket": deps.settings.polymarket_leg_weight,
    }
    consensus = weighted_consensus([(legs[name], weights[name]) for name in legs])
    payload: dict[str, Any] = {
        "market": "outrights",
        "consensus": _round4(consensus),
        "legs": {name: _round4(probs) for name, probs in legs.items()},
        "weights": weights,
        "credits_remaining": credits_remaining,
        **freshness,
    }
    if bookmaker_error is not None:
        payload["bookmaker_leg_error"] = bookmaker_error
    return payload


async def _h2h_payload(deps: AgentDeps) -> dict[str, Any]:
    response = await run_with_timeout(
        deps.odds.h2h(),
        tool_name="get_odds",
        timeout_seconds=deps.settings.tool_timeout_seconds,
    )
    events = [
        {
            "home": event.home_team,
            "away": event.away_team,
            "commence_time": event.commence_time.isoformat() if event.commence_time else None,
            "consensus": _round4(event_consensus(event, market_key="h2h")),
        }
        for event in response.events
    ]
    return {
        "market": "h2h",
        "events": events,
        "credits_remaining": response.credits.remaining,
        **_freshness(response.events, market_key="h2h"),
    }


async def _get_odds(args: GetOddsArgs, deps: AgentDeps) -> ToolResult[Any]:
    if cached := deps.market_cache.get(args.market):
        return ToolResult(payload=cached)
    async with deps.market_cache_lock:
        if cached := deps.market_cache.get(args.market):
            return ToolResult(payload=cached)
        deps.runtime.charge_data_fetch()
        with deps.runtime.observe(kind="data_fetch", actor=deps.actor, name=f"get_odds:{args.market}") as rec:
            payload = await (_outrights_payload(deps) if args.market == "outrights" else _h2h_payload(deps))
            deps.market_cache[args.market] = payload
            rec.set_output({"market": args.market})
            rec.note(
                summary=f"odds {args.market}: {payload['credits_remaining']} credits left",
                market=args.market,
                credits_remaining=payload["credits_remaining"],
            )
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="get_odds",
    description=(
        "Market consensus probabilities. 'outrights' blends two legs in weighted log-odds: de-vigged bookmaker "
        "consensus (power-method de-vig, log-odds averaging across books) and normalised Polymarket winner prices; "
        "both legs are reported separately, keyed by team id. If bookmaker odds are unavailable the consensus "
        "falls back to Polymarket alone and a 'bookmaker_leg_error' field is set. "
        "'h2h' gives match win/draw/loss per bookmaker event. "
        "fetched_at and prices_updated_oldest/newest report when the response was pulled and when bookmakers last "
        "re-priced, so you can tell whether a news event is already in the price. "
        "This is your calibration anchor: always state the market number before diverging from it."
    ),
    args_model=GetOddsArgs,
    fn=_get_odds,
)
