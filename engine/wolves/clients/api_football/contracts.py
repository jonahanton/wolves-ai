from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MatchStatus = Literal["scheduled", "live", "finished", "abandoned"]
MatchPeriod = Literal["regulation", "extra_time", "shootout"]
WinnerSide = Literal["home", "away"]


class GoalEvent(BaseModel):
    minute: int
    side: WinnerSide


class MatchFixture(BaseModel):
    fixture_id: int
    kickoff: datetime
    status: MatchStatus
    home: str
    away: str
    home_goals: int | None = None
    away_goals: int | None = None
    # Regulation (90-minute) score, distinct from home/away_goals once a knockout goes to extra time.
    fulltime_home: int | None = None
    fulltime_away: int | None = None
    elapsed: int | None = None
    period: MatchPeriod = "regulation"
    home_reds: int = 0
    away_reds: int = 0
    goals: list[GoalEvent] = []
    home_shots_on: int | None = None
    away_shots_on: int | None = None
    home_total_shots: int | None = None
    away_total_shots: int | None = None
    home_possession: float | None = None
    away_possession: float | None = None
    city: str | None = None
    winner: WinnerSide | None = None


class FixturesClient(ABC):
    """Tournament fixtures and results provider."""

    @abstractmethod
    async def fixtures(self, *, date: str | None = None) -> list[MatchFixture]:
        """Return World Cup fixtures, optionally for a single YYYY-MM-DD date."""

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None
