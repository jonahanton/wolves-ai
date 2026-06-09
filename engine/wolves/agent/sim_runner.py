"""The frozen sim interface the harness builds against."""

from __future__ import annotations

from typing import Protocol

from wolves.sim import api
from wolves.sim.api import SimOutputs


class SimulationApi(Protocol):
    def run_simulation(
        self,
        rating_overrides: dict[str, float],
        fixture_goal_offsets: dict[int, tuple[float, float]],
        n_sims: int,
        seed: int | None,
    ) -> SimOutputs: ...


class EngineSimulation:
    """The production implementation: the full tournament simulation."""

    def run_simulation(
        self,
        rating_overrides: dict[str, float],
        fixture_goal_offsets: dict[int, tuple[float, float]],
        n_sims: int,
        seed: int | None,
    ) -> SimOutputs:
        return api.run_simulation(rating_overrides, fixture_goal_offsets, n_sims, seed)
