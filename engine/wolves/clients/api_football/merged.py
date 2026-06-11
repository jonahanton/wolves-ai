from __future__ import annotations

from .contracts import FixturesClient, MatchFixture


class MergedFixturesClient(FixturesClient):
    """Union of the live poll and previously stored fixtures; the live poll wins on overlap."""

    def __init__(self, inner: FixturesClient, *, stored: list[MatchFixture]) -> None:
        self._inner = inner
        self._stored = stored

    async def fixtures(self, *, date: str | None = None) -> list[MatchFixture]:
        polled = await self._inner.fixtures(date=date)
        merged = {f.fixture_id: f for f in self._stored if date is None or f.kickoff.date().isoformat() == date}
        merged |= {f.fixture_id: f for f in polled}
        return sorted(merged.values(), key=lambda f: (f.kickoff, f.fixture_id))

    async def aclose(self) -> None:
        await self._inner.aclose()
