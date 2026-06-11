from __future__ import annotations

from datetime import datetime

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.clients.api_football import FakeFixturesClient, MatchFixture
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.live import live_pass
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.results_store import ResultsStore


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


def _forecaster(settings: Settings) -> Forecaster:
    instance = Forecaster(settings)
    instance._state = synthetic_state()
    return instance


async def test_live_pass_persists_the_polled_result_for_later_runs(tmp_path):
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    fixtures = FakeFixturesClient(matches=[_finished_match_one()])

    assert await live_pass(settings, fixtures=fixtures, n_sims=200, seed=5, forecaster=_forecaster(settings)) is True

    stored = ResultsStore(ArtifactStore(settings)).load()
    assert stored.results[1].home_goals == 2 and stored.results[1].away_goals == 0
    assert [f.fixture_id for f in stored.fixtures] == [1300001]
    assert stored.fetched_at
