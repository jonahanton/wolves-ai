from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class Outcome(BaseModel):
    name: str
    price: float


class Market(BaseModel):
    key: str
    last_update: datetime | None = None
    outcomes: list[Outcome] = Field(default_factory=list)


class Bookmaker(BaseModel):
    key: str
    title: str
    markets: list[Market] = Field(default_factory=list)


class OddsEvent(BaseModel):
    id: str
    sport_key: str
    commence_time: datetime | None = None
    home_team: str | None = None
    away_team: str | None = None
    bookmakers: list[Bookmaker] = Field(default_factory=list)


class CreditUsage(BaseModel):
    """Credit accounting reported by The Odds API response headers."""

    used: int | None = None
    remaining: int | None = None
    last_cost: int | None = None


class OddsResponse(BaseModel):
    events: list[OddsEvent] = Field(default_factory=list)
    credits: CreditUsage = Field(default_factory=CreditUsage)


class OddsClient(ABC):
    """Bookmaker odds provider. Implementations do I/O only; de-vig and
    consensus live in pure modules."""

    @abstractmethod
    async def outrights(self) -> OddsResponse: ...

    @abstractmethod
    async def h2h(self) -> OddsResponse: ...

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None
