from __future__ import annotations

import pytest

from wolves.config import Settings
from wolves.run import generate_snapshot


@pytest.fixture(scope="session")
def snapshot():
    return generate_snapshot(Settings(), n_sims=2000, seed=42)
