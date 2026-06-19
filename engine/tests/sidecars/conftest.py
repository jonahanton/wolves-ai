from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.forecast import Forecaster
from wolves.sidecars import SidecarInputs
from wolves.sim.engine import EloMatchEngine
from wolves.sim.format import PlayedResult, load_format
from wolves.sim.mc import run_tournament

PLAYED_MATCH = 1
N_SIMS = 2000
PARAMETER_DRAWS = 50
WDL_CURVE_DRAWS = 300


@pytest.fixture(scope="session")
def fmt():
    return load_format(Settings().data_dir)


@pytest.fixture(scope="session")
def forecaster() -> Forecaster:
    base = synthetic_state()
    cov = np.eye(len(base.strengths) + 2) * 0.02
    instance = Forecaster(Settings(storage_mode="local"))
    instance._state = dataclasses.replace(base, covariance=cov)
    return instance


@pytest.fixture(scope="session")
def inputs(fmt, forecaster) -> SidecarInputs:
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
        forecaster=forecaster,
        world_specs={"baseline": ((), ()), "upset": ((), ())},
        wdl_curve_draws=WDL_CURVE_DRAWS,
        played=frozenset({PLAYED_MATCH}),
    )
