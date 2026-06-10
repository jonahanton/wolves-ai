from __future__ import annotations

from datetime import datetime

from wolves.clients.api_football import FakeFixturesClient, MatchFixture
from wolves.config import Settings
from wolves.live import live_pass


def _finished_match_one() -> MatchFixture:
    return MatchFixture(
        fixture_id=1300001,
        kickoff=datetime.fromisoformat("2026-06-11T13:00:00-06:00"),
        status="finished",
        home="Mexico",
        away="South Africa",
        home_goals=2,
        away_goals=0,
    )


async def test_second_pass_with_the_same_results_writes_nothing(tmp_path):
    settings = Settings(runs_root=tmp_path)
    fixtures = FakeFixturesClient(matches=[_finished_match_one()])

    assert await live_pass(settings, fixtures=fixtures, n_sims=120, seed=2) is True
    written = sorted(p.name for p in tmp_path.glob("*.json"))

    assert await live_pass(settings, fixtures=fixtures, n_sims=120, seed=2) is False
    assert sorted(p.name for p in tmp_path.glob("*.json")) == written


async def test_pass_with_no_finished_results_writes_nothing(tmp_path):
    settings = Settings(runs_root=tmp_path)
    fixtures = FakeFixturesClient(matches=[])

    assert await live_pass(settings, fixtures=fixtures, n_sims=120, seed=2) is False
    assert not (tmp_path / "latest.json").exists()
