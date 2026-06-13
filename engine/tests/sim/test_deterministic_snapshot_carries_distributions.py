from __future__ import annotations

from wolves.config import Settings
from wolves.run import generate_snapshot


def test_deterministic_snapshot_carries_distributions(tmp_path_factory) -> None:
    settings = Settings(runs_root=tmp_path_factory.mktemp("runs"), storage_mode="local")
    snapshot, sidecars = generate_snapshot(settings, n_sims=2000, seed=42)

    if snapshot.champion is None:
        # The Elo baseline path carries no parameter covariance and publishes no block.
        assert snapshot.distributions is None
        return
    block = snapshot.distributions
    assert block is not None
    assert block.provenance == "parameters_only"
    assert block.n_worlds == 1
    assert not snapshot.intervals
    assert set(sidecars) >= {"distributions", "bracket-samples", "pairing-matrices", "match-wdl-draws"}
