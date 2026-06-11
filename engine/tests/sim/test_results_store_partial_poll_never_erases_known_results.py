from __future__ import annotations

from datetime import datetime

from wolves.clients.api_football import MatchFixture
from wolves.config import Settings
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import PlayedResult
from wolves.sim.results_store import ResultsStore


def _result(match: int, home: int, away: int) -> PlayedResult:
    return PlayedResult(match=match, home_goals=home, away_goals=away)


def _fixture(fixture_id: int) -> MatchFixture:
    return MatchFixture(
        fixture_id=fixture_id,
        kickoff=datetime.fromisoformat("2026-06-11T13:00:00-06:00"),
        status="finished",
        home="Mexico",
        away="South Africa",
        home_goals=2,
        away_goals=0,
    )


def test_partial_poll_never_erases_known_results(tmp_path):
    store = ResultsStore(ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local")))
    store.record({1: _result(1, 2, 0), 2: _result(2, 1, 1)}, fixtures=[_fixture(101)])

    merged = store.record({3: _result(3, 0, 3)}, fixtures=[_fixture(102)])

    assert set(merged.results) == {1, 2, 3}
    reloaded = store.load()
    assert reloaded.results[1] == _result(1, 2, 0)
    assert {f.fixture_id for f in reloaded.fixtures} == {101, 102}
