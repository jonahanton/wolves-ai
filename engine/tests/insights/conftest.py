from __future__ import annotations

import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import Forecaster


@pytest.fixture()
def forecaster(tmp_path) -> Forecaster:
    """Real 48-team format with a flat synthetic state; no dataset fit needed."""
    instance = Forecaster(Settings(runs_root=tmp_path, agent_state_bucket=""))
    # Test seam: bypasses fit() so no dataset is needed for simulation contracts.
    instance._state = synthetic_state()
    return instance
