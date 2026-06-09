from __future__ import annotations

import json
from pathlib import Path

from .contracts import CreditUsage, OddsClient, OddsEvent, OddsResponse
from .polymarket import PolymarketClient, PolymarketMarket, markets_from_events

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[OddsEvent]:
    raw = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    return [OddsEvent.model_validate(item) for item in raw]


class FakeOddsClient(OddsClient):
    """Deterministic odds client backed by the recorded fixtures. No network."""

    def __init__(
        self,
        *,
        outright_events: list[OddsEvent] | None = None,
        h2h_events: list[OddsEvent] | None = None,
    ) -> None:
        self._outrights = outright_events if outright_events is not None else _load("outrights.json")
        self._h2h = h2h_events if h2h_events is not None else _load("h2h.json")
        self.calls: list[str] = []

    async def outrights(self) -> OddsResponse:
        self.calls.append("outrights")
        return OddsResponse(
            events=self._outrights,
            credits=CreditUsage(used=len(self.calls), remaining=500 - len(self.calls), last_cost=1),
        )

    async def h2h(self) -> OddsResponse:
        self.calls.append("h2h")
        return OddsResponse(
            events=self._h2h,
            credits=CreditUsage(used=len(self.calls), remaining=500 - len(self.calls), last_cost=1),
        )


class FakePolymarketClient(PolymarketClient):
    """Deterministic Polymarket client backed by the recorded Gamma fixture. No network."""

    def __init__(self, *, markets: list[PolymarketMarket] | None = None) -> None:
        if markets is not None:
            self._markets = markets
        else:
            payload = json.loads((_FIXTURES / "polymarket-winner.json").read_text(encoding="utf-8"))
            self._markets = markets_from_events(payload)
        self.calls = 0

    async def winner_markets(self) -> list[PolymarketMarket]:
        self.calls += 1
        return list(self._markets)
