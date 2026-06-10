"""Market outright consensus for the published blend: bookmaker outrights and
Polymarket title prices, de-vigged, combined in weighted log-odds."""

from __future__ import annotations

import logging

from wolves.clients.odds import (
    FakeOddsClient,
    OddsClient,
    PolymarketClient,
    event_consensus,
    team_id_for_name,
    winner_probabilities,
)
from wolves.clients.odds.client import TheOddsApiClient
from wolves.clients.odds.polymarket import GammaPolymarketClient
from wolves.config import Settings
from wolves.markets.devig import weighted_consensus
from wolves.sim.format import FormatData

logger = logging.getLogger(__name__)


def build_clients(settings: Settings) -> tuple[OddsClient, PolymarketClient]:
    odds = TheOddsApiClient(settings.odds_api_key) if settings.odds_api_key else FakeOddsClient()
    return odds, GammaPolymarketClient()


async def outright_consensus(
    settings: Settings, fmt: FormatData, *, odds: OddsClient, polymarket: PolymarketClient
) -> dict[str, float]:
    """De-vigged title probabilities by team id; empty when no source maps."""
    teams = list(fmt.teams)
    legs: list[tuple[dict[str, float], float]] = []

    response = await odds.outrights()
    book_probs: dict[str, float] = {}
    for event in response.events:
        for name, prob in event_consensus(event, market_key="outrights").items():
            team_id = team_id_for_name(name, teams)
            if team_id is not None:
                book_probs[team_id] = prob
    if book_probs:
        total = sum(book_probs.values())
        legs.append(({k: v / total for k, v in book_probs.items()}, settings.bookmaker_leg_weight))

    poly = winner_probabilities(await polymarket.winner_markets(), teams)
    if poly:
        legs.append((poly, settings.polymarket_leg_weight))

    if not legs:
        logger.warning("no market outright legs available; blend will be model-only")
        return {}
    return weighted_consensus(legs)
