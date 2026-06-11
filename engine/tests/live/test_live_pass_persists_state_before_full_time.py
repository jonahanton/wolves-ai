from __future__ import annotations

from tests.live.live_fakes import FakeLiveForecaster, live_fixture
from wolves.clients.api_football import FakeFixturesClient
from wolves.config import Settings
from wolves.live import live_pass
from wolves.live_state import LiveStateStore
from wolves.s3.artifacts import ArtifactStore


async def test_live_pass_persists_state_even_before_full_time_results(tmp_path) -> None:
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    forecaster = FakeLiveForecaster()

    published = await live_pass(
        settings,
        fixtures=FakeFixturesClient([live_fixture(goals=(1, 0), elapsed=68)]),
        n_sims=200,
        forecaster=forecaster,
    )

    state = LiveStateStore(ArtifactStore(settings)).load()
    assert published is False
    assert state is not None
    assert state.live_match_count == 1
    assert state.fixtures[0].forecast.source == "in_match"
