from __future__ import annotations

import json

import pytest

from wolves.config import Settings, get_settings
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import PlayedResult, load_results
from wolves.sim.results_store import ResultsStore


@pytest.fixture
def pinned_runs_root(tmp_path, monkeypatch):
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("RUNS_ROOT", str(runs_root))
    get_settings.cache_clear()
    yield runs_root
    get_settings.cache_clear()


def test_persisted_result_overrides_the_static_file_and_new_matches_join(tmp_path, pinned_runs_root):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "results.json").write_text(
        json.dumps({"results": [{"match": 1, "homeGoals": 1, "awayGoals": 0}]}), encoding="utf-8"
    )
    store = ResultsStore(ArtifactStore(Settings(runs_root=pinned_runs_root, storage_mode="local")))
    store.record(
        {
            1: PlayedResult(match=1, home_goals=2, away_goals=0),
            2: PlayedResult(match=2, home_goals=0, away_goals=0),
        }
    )

    results = load_results(data_dir)

    assert results[1] == PlayedResult(match=1, home_goals=2, away_goals=0)
    assert results[2] == PlayedResult(match=2, home_goals=0, away_goals=0)
