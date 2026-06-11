from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MatchStatus = Literal["scheduled", "live", "finished", "abandoned"]
WinnerSide = Literal["home", "away"]


class MatchFixture(BaseModel):
    fixture_id: int
    kickoff: datetime
    status: MatchStatus
    home: str
    away: str
    home_goals: int | None = None
    away_goals: int | None = None
    elapsed: int | None = None
    home_reds: int = 0
    away_reds: int = 0
    city: str | None = None
    winner: WinnerSide | None = None


class FixturesClient(ABC):
    """Tournament fixtures and results provider."""

    @abstractmethod
    async def fixtures(self, *, date: str | None = None) -> list[MatchFixture]:
        """Return World Cup fixtures, optionally for a single YYYY-MM-DD date."""

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None
