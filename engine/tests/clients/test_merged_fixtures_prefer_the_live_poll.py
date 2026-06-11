from __future__ import annotations

from datetime import datetime

from wolves.clients.api_football import FakeFixturesClient, MatchFixture, MergedFixturesClient


def _fixture(fixture_id: int, *, day: str, home_goals: int) -> MatchFixture:
    return MatchFixture(
        fixture_id=fixture_id,
        kickoff=datetime.fromisoformat(f"{day}T13:00:00+00:00"),
        status="finished",
        home="Mexico",
        away="South Africa",
        home_goals=home_goals,
        away_goals=0,
    )


async def test_stored_fixtures_surface_and_the_live_poll_wins_on_overlap():
    stored = [_fixture(1, day="2026-06-11", home_goals=2), _fixture(2, day="2026-06-12", home_goals=1)]
    polled = [_fixture(1, day="2026-06-11", home_goals=3)]
    client = MergedFixturesClient(FakeFixturesClient(matches=polled), stored=stored)

    merged = {f.fixture_id: f for f in await client.fixtures()}
    assert set(merged) == {1, 2}
    assert merged[1].home_goals == 3

    on_day = await client.fixtures(date="2026-06-12")
    assert [f.fixture_id for f in on_day] == [2]
