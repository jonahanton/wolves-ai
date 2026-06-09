from __future__ import annotations

import logging
from typing import Any

import httpx

from wolves.connectors._http import _raise_for_status, async_retrying

from .contracts import CreditUsage, OddsClient, OddsEvent, OddsResponse

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.the-odds-api.com/v4"
OUTRIGHTS_SPORT = "soccer_fifa_world_cup_winner"
H2H_SPORT = "soccer_fifa_world_cup"


def _credits_from_headers(headers: httpx.Headers) -> CreditUsage:
    def read(name: str) -> int | None:
        value = headers.get(name)
        try:
            return int(float(value)) if value is not None else None
        except ValueError:
            return None

    return CreditUsage(
        used=read("x-requests-used"),
        remaining=read("x-requests-remaining"),
        last_cost=read("x-requests-last"),
    )


class TheOddsApiClient(OddsClient):
    """The Odds API v4. Credits burn per region x market, so each call requests
    one region and one market and the consumed credits are logged."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
        regions: str = "eu",
    ) -> None:
        self._api_key = api_key
        self._regions = regions
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def outrights(self) -> OddsResponse:
        return await self._odds(OUTRIGHTS_SPORT, "outrights")

    async def h2h(self) -> OddsResponse:
        return await self._odds(H2H_SPORT, "h2h")

    async def _odds(self, sport_key: str, markets: str) -> OddsResponse:
        params: dict[str, Any] = {
            "apiKey": self._api_key,
            "regions": self._regions,
            "markets": markets,
            "oddsFormat": "decimal",
        }
        url = f"{_BASE_URL}/sports/{sport_key}/odds"
        async for attempt in async_retrying():
            with attempt:
                response = await self._client.get(url, params=params)
                _raise_for_status(response)
                usage = _credits_from_headers(response.headers)
                logger.info(
                    "odds %s/%s: %s credits consumed, %s remaining",
                    sport_key,
                    markets,
                    usage.last_cost,
                    usage.remaining,
                )
                events = [OddsEvent.model_validate(item) for item in response.json()]
                return OddsResponse(events=events, credits=usage)
        return OddsResponse()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
