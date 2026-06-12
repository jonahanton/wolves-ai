from __future__ import annotations

from datetime import date

import numpy as np

from wolves.config import Settings
from wolves.models.contracts import FittedState
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.fitted import FittedStateStore


def _state() -> FittedState:
    return FittedState(
        model_id="poisson-decay",
        version="3",
        dataset_id="abc123def456",
        as_of=date(2026, 6, 12),
        teams=("brazil", "england", "france"),
        strengths=np.array([0.31415926535897932, -0.05, 0.2718281828459045]),
        globals_={"intercept": 0.123456789012345, "home_adv": 0.21, "rho": -0.06},
        covariance=np.array([[0.04, 0.001], [0.001, 0.0025]]),
        diagnostics={"log_lik": -1234.5678},
    )


def test_fitted_state_round_trips_through_store_and_pointer(tmp_path):
    store = FittedStateStore(ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local")))
    state = _state()

    key = store.publish(state, run_id="run-20260612")

    assert key == "models/fitted/run-20260612.json"
    pointer = store.latest_pointer()
    assert pointer is not None
    assert pointer.run_id == "run-20260612"
    assert pointer.dataset_id == state.dataset_id
    assert pointer.as_of == state.as_of

    loaded = store.load()
    assert loaded is not None
    assert loaded.model_id == state.model_id
    assert loaded.version == state.version
    assert loaded.teams == state.teams
    np.testing.assert_array_equal(loaded.strengths, state.strengths)
    np.testing.assert_array_equal(loaded.covariance, state.covariance)
    assert loaded.globals_ == state.globals_
    assert loaded.diagnostics == state.diagnostics


def test_load_returns_none_before_any_publish(tmp_path):
    store = FittedStateStore(ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local")))
    assert store.load() is None
    assert store.latest_pointer() is None
