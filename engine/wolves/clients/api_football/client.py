from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from wolves.connectors._http import _raise_for_status, async_retrying

from .contracts import FixturesClient, MatchFixture, MatchStatus, WinnerSide

_BASE_URL = "https://v3.football.api-sports.io"
WORLD_CUP_LEAGUE_ID = 1
SEASON = 2026

_FINISHED = {"FT", "AET", "PEN"}
_LIVE = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE"}
_ABANDONED = {"ABD", "CANC", "INT", "PST", "SUSP", "AWD", "WO"}


class ApiFootballPayloadError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _status(short: str) -> MatchStatus:
    if short in _FINISHED:
        return "finished"
    if short in _LIVE:
        return "live"
    if short in _ABANDONED:
        return "abandoned"
    return "scheduled"


def _winner(teams: dict[str, Any]) -> WinnerSide | None:
    if (teams.get("home") or {}).get("winner"):
        return "home"
    if (teams.get("away") or {}).get("winner"):
        return "away"
    return None


def _to_fixture(item: dict[str, Any]) -> MatchFixture:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    goals = item.get("goals") or {}
    venue = fixture.get("venue") or {}
    status = fixture.get("status") or {}
    return MatchFixture(
        fixture_id=int(fixture.get("id") or 0),
        kickoff=datetime.fromisoformat(fixture.get("date")),
        status=_status((status.get("short")) or ""),
        home=(teams.get("home") or {}).get("name") or "",
        away=(teams.get("away") or {}).get("name") or "",
        home_goals=goals.get("home"),
        away_goals=goals.get("away"),
        elapsed=status.get("elapsed"),
        city=venue.get("city"),
        winner=_winner(teams),
    )


class ApiFootballClient(FixturesClient):
    """API-Football (api-sports) v3. The free tier allows 100 requests per day,
    so callers should batch by date rather than poll per match."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def fixtures(self, *, date: str | None = None) -> list[MatchFixture]:
        params: dict[str, Any] = {"league": WORLD_CUP_LEAGUE_ID, "season": SEASON}
        if date:
            params["date"] = date
        headers = {"x-apisports-key": self._api_key}
        async for attempt in async_retrying():
            with attempt:
                response = await self._client.get(f"{_BASE_URL}/fixtures", params=params, headers=headers)
                _raise_for_status(response)
                payload = response.json()
                errors = payload.get("errors")
                if errors:
                    raise ApiFootballPayloadError(str(errors))
                items = payload.get("response") or []
                if date is None and not items:
                    raise ApiFootballPayloadError("API-Football returned no World Cup fixtures")
                return [_to_fixture(item) for item in items]
        return []

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
