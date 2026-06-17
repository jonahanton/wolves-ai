from __future__ import annotations

import numpy as np
import pytest

from wolves.config import Settings
from wolves.sidecars import SidecarInputs
from wolves.sim.engine import EloMatchEngine
from wolves.sim.format import PlayedResult, load_format
from wolves.sim.mc import run_tournament

PLAYED_MATCH = 1
N_SIMS = 2000
PARAMETER_DRAWS = 50


@pytest.fixture(scope="session")
def fmt():
    return load_format(Settings().data_dir)


@pytest.fixture(scope="session")
def inputs(fmt) -> SidecarInputs:
    base = np.linspace(2100.0, 1500.0, len(fmt.teams))
    results = {PLAYED_MATCH: PlayedResult(match=PLAYED_MATCH, home_goals=2, away_goals=1)}
    per_world = {
        name: run_tournament(fmt, EloMatchEngine(fmt, base), n_sims=N_SIMS, seed=seed, results=results)
        for name, seed in (("baseline", 11), ("upset", 12))
    }
    return SidecarInputs(
        fmt=fmt,
        per_world_results=per_world,
        weights={"baseline": 0.7, "upset": 0.3},
        parameter_draws=PARAMETER_DRAWS,
        rng_seed=99,
        played=frozenset({PLAYED_MATCH}),
    )
