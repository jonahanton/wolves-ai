from __future__ import annotations

import pytest

from wolves.config import Settings
from wolves.run import generate_snapshot


@pytest.fixture(scope="session")
def snapshot(tmp_path_factory):
    # A fresh runs root pins the Elo baseline path, hermetic from local scratch state.
    settings = Settings(runs_root=tmp_path_factory.mktemp("runs"), storage_mode="local")
    return generate_snapshot(settings, n_sims=2000, seed=42)
