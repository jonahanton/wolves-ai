from __future__ import annotations

import json
from pathlib import Path

from .client import _to_fixture
from .contracts import FixturesClient, MatchFixture

_FIXTURES = Path(__file__).parent / "fixtures"


class FakeFixturesClient(FixturesClient):
    """Deterministic fixtures client backed by the recorded fixture. No network."""

    def __init__(self, matches: list[MatchFixture] | None = None) -> None:
        if matches is None:
            raw = json.loads((_FIXTURES / "fixtures.json").read_text(encoding="utf-8"))
            matches = [_to_fixture(item) for item in raw["response"]]
        self._matches = matches
        self.calls: list[str | None] = []

    async def fixtures(self, *, date: str | None = None) -> list[MatchFixture]:
        self.calls.append(date)
        if date is None:
            return list(self._matches)
        return [m for m in self._matches if m.kickoff.date().isoformat() == date]
