from __future__ import annotations

from datetime import datetime

import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.clients.api_football import FakeFixturesClient, MatchFixture
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.live import ApiFootballKeyMissingError, DemoFixturesNotLocalError, build_fixtures_client, live_pass
from wolves.live_state import LiveStateStore
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


async def test_demo_pass_updates_live_state_but_records_and_publishes_nothing(tmp_path):
    settings = Settings(runs_root=tmp_path, storage_mode="local", fixtures_demo=True)
    fixtures = FakeFixturesClient(matches=[_finished_match_one()])

    published = await live_pass(settings, fixtures=fixtures, n_sims=200, seed=5, forecaster=_forecaster(settings))

    assert published is False
    artifacts = ArtifactStore(settings)
    stored = ResultsStore(artifacts).load()
    assert stored.results == {} and stored.fixtures == []
    assert not list((tmp_path / "snapshots").rglob("*.json")) if (tmp_path / "snapshots").exists() else True
    assert LiveStateStore(artifacts).load() is not None


def test_keyless_client_build_raises_instead_of_degrading_to_canned_fixtures():
    with pytest.raises(ApiFootballKeyMissingError):
        build_fixtures_client(Settings(api_football_key="", fixtures_demo=False))


def test_demo_fixtures_refuse_cloud_storage():
    with pytest.raises(DemoFixturesNotLocalError):
        build_fixtures_client(Settings(fixtures_demo=True, storage_mode="both"))
