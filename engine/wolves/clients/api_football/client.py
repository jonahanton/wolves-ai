from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from wolves.connectors._http import _raise_for_status, async_retrying

from .contracts import FixturesClient, GoalEvent, MatchFixture, MatchPeriod, MatchStatus, WinnerSide

_BASE_URL = "https://v3.football.api-sports.io"
WORLD_CUP_LEAGUE_ID = 1
SEASON = 2026

# AWD/WO carry goals and a winner; SUSP/INT resume with a frozen clock; PST replays as scheduled.
_FINISHED = {"FT", "AET", "PEN", "AWD", "WO"}
_LIVE = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "SUSP", "INT"}
_ABANDONED = {"ABD", "CANC"}
_EXTRA_TIME = {"ET", "BT"}
_IDS_BATCH = 20


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


def _period(short: str) -> MatchPeriod:
    if short in _EXTRA_TIME:
        return "extra_time"
    if short == "P":
        return "shootout"
    return "regulation"


def _winner(teams: dict[str, Any]) -> WinnerSide | None:
    if (teams.get("home") or {}).get("winner"):
        return "home"
    if (teams.get("away") or {}).get("winner"):
        return "away"
    return None


def _red_cards(item: dict[str, Any]) -> tuple[int, int]:
    home_id = ((item.get("teams") or {}).get("home") or {}).get("id")
    home = away = 0
    for event in item.get("events") or []:
        if (event.get("type") or "").casefold() != "card":
            continue
        if "red" not in (event.get("detail") or "").casefold():
            continue
        if ((event.get("team") or {}).get("id")) == home_id:
            home += 1
        else:
            away += 1
    return home, away


def _goal_events(item: dict[str, Any]) -> list[GoalEvent]:
    """Open-play and penalty goals in order; own goals credit the opponent.
    Shootout conversions carry the same Goal type but resolve the tie rather than
    the scoreline, so they are excluded via their Penalty Shootout comment."""
    home_id = ((item.get("teams") or {}).get("home") or {}).get("id")
    goals: list[GoalEvent] = []
    for event in item.get("events") or []:
        if (event.get("type") or "").casefold() != "goal":
            continue
        detail = (event.get("detail") or "").casefold()
        if "missed" in detail:
            continue
        if "shootout" in (event.get("comments") or "").casefold():
            continue
        minute = (event.get("time") or {}).get("elapsed")
        if minute is None:
            continue
        scored_by_home = ((event.get("team") or {}).get("id")) == home_id
        if "own goal" in detail:
            scored_by_home = not scored_by_home
        goals.append(GoalEvent(minute=int(minute), side="home" if scored_by_home else "away"))
    goals.sort(key=lambda g: g.minute)
    return goals


def _to_fixture(item: dict[str, Any]) -> MatchFixture:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    goals = item.get("goals") or {}
    venue = fixture.get("venue") or {}
    status = fixture.get("status") or {}
    short = (status.get("short")) or ""
    home_reds, away_reds = _red_cards(item)
    return MatchFixture(
        fixture_id=int(fixture.get("id") or 0),
        kickoff=datetime.fromisoformat(fixture.get("date")),
        status=_status(short),
        home=(teams.get("home") or {}).get("name") or "",
        away=(teams.get("away") or {}).get("name") or "",
        home_goals=goals.get("home"),
        away_goals=goals.get("away"),
        elapsed=status.get("elapsed"),
        period=_period(short),
        home_reds=home_reds,
        away_reds=away_reds,
        goals=_goal_events(item),
        city=venue.get("city"),
        winner=_winner(teams),
    )


class ApiFootballClient(FixturesClient):
    """API-Football (api-sports) v3. A 60s live loop exceeds the 100-per-day free tier; needs a paid plan."""

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
        items = await self._fetch_all_pages(params)
        if date is None and not items:
            raise ApiFootballPayloadError("API-Football returned no World Cup fixtures")
        fixtures = [_to_fixture(item) for item in items]
        return await self._with_live_events(fixtures)

    async def _fetch_all_pages(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        items = []
        page = 1
        while True:
            payload = await self._get({**params, "page": page} if page > 1 else params)
            items.extend(payload.get("response") or [])
            paging = payload.get("paging") or {}
            if page >= int(paging.get("total") or 1):
                return items
            page += 1

    async def _with_live_events(self, fixtures: list[MatchFixture]) -> list[MatchFixture]:
        """Re-fetch live fixtures by id: only by-ids responses carry card events."""
        live_ids = [f.fixture_id for f in fixtures if f.status == "live"]
        if not live_ids:
            return fixtures
        enriched: dict[int, MatchFixture] = {}
        for start in range(0, len(live_ids), _IDS_BATCH):
            batch = live_ids[start : start + _IDS_BATCH]
            payload = await self._get({"ids": "-".join(str(i) for i in batch)})
            for item in payload.get("response") or []:
                fixture = _to_fixture(item)
                enriched[fixture.fixture_id] = fixture
        return [enriched.get(f.fixture_id, f) for f in fixtures]

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"x-apisports-key": self._api_key}
        async for attempt in async_retrying():
            with attempt:
                response = await self._client.get(f"{_BASE_URL}/fixtures", params=params, headers=headers)
                _raise_for_status(response)
                payload = response.json()
                errors = payload.get("errors")
                if errors:
                    raise ApiFootballPayloadError(str(errors))
                return payload
        raise ApiFootballPayloadError("API-Football retries exhausted")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
