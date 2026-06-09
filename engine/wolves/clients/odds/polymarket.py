from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

from wolves.connectors._http import _raise_for_status, async_retrying

from .team_names import NamedTeam, team_id_in_text

logger = logging.getLogger(__name__)

_BASE_URL = "https://gamma-api.polymarket.com"
WINNER_SLUG = "world-cup-winner"


class PolymarketMarket(BaseModel):
    question: str
    yes_price: float


class PolymarketClient(ABC):
    """Prediction-market winner prices. Implementations do I/O only; name
    mapping and normalisation live in pure functions."""

    @abstractmethod
    async def winner_markets(self) -> list[PolymarketMarket]: ...

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None


def markets_from_events(payload: list[dict[str, Any]]) -> list[PolymarketMarket]:
    """Parse Gamma event payloads; outcomePrices is a JSON-string array with the Yes price first."""
    markets: list[PolymarketMarket] = []
    for event in payload:
        for market in event.get("markets", []):
            prices = json.loads(market.get("outcomePrices") or "[]")
            if not prices:
                continue
            markets.append(PolymarketMarket(question=market.get("question", ""), yes_price=float(prices[0])))
    return markets


def winner_probabilities(markets: list[PolymarketMarket], teams: list[NamedTeam]) -> dict[str, float]:
    """Map market questions to team ids and normalise Yes prices to sum to 1.

    Markets for non-qualified teams are expected and dropped silently; a
    qualified team without a market is a name-mapping failure that silently
    inflates every rival, so it is warned about loudly.
    """
    raw: dict[str, float] = {}
    for market in markets:
        team_id = team_id_in_text(market.question, teams)
        if team_id is None:
            logger.debug("unmapped polymarket market dropped: %s", market.question)
            continue
        raw[team_id] = raw.get(team_id, 0.0) + market.yes_price
    missing = sorted({team.id for team in teams} - raw.keys())
    if missing:
        logger.warning("no polymarket market mapped for qualified team(s) %s; rivals inflate", missing)
    total = sum(raw.values())
    if total <= 0.0:
        return {}
    return {team_id: price / total for team_id, price in raw.items()}


class GammaPolymarketClient(PolymarketClient):
    """Polymarket's public Gamma API; no key and no credit accounting."""

    def __init__(self, *, client: httpx.AsyncClient | None = None, timeout: float = 20.0) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def winner_markets(self) -> list[PolymarketMarket]:
        async for attempt in async_retrying():
            with attempt:
                response = await self._client.get(f"{_BASE_URL}/events", params={"slug": WINNER_SLUG})
                _raise_for_status(response)
                markets = markets_from_events(response.json())
                logger.info("polymarket %s: %d market(s)", WINNER_SLUG, len(markets))
                return markets
        return []

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
