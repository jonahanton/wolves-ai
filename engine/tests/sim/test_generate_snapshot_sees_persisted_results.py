from __future__ import annotations

from wolves.config import Settings
from wolves.run import generate_snapshot
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import PlayedResult
from wolves.sim.results_store import ResultsStore


def test_generate_snapshot_treats_a_persisted_result_as_played(tmp_path):
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    ResultsStore(ArtifactStore(settings)).record({1: PlayedResult(match=1, home_goals=2, away_goals=0)})

    snapshot = generate_snapshot(settings, n_sims=200, seed=7)

    assert 1 not in {entry.match for entry in snapshot.matches}
