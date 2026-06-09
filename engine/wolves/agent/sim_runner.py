"""The frozen sim interface the harness builds against.

WS-A is delivering ``wolves.sim.api.run_simulation(rating_overrides,
fixture_goal_offsets, n_sims, seed) -> SimOutputs``. Until it merges, this
module defines the protocol and wires the M0 ``run_tournament`` behind it
as the placeholder implementation.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from pydantic import BaseModel, Field

from wolves.sim.format import FormatData
from wolves.sim.mc import run_tournament
from wolves.sim.outputs import build_england, build_slots
from wolves.snapshot import EnglandBlock, Slot


class SimOutputs(BaseModel):
    n_sims: int
    england: EnglandBlock
    slots: list[Slot] = Field(default_factory=list)


class SimulationApi(Protocol):
    def run_simulation(
        self,
        rating_overrides: dict[str, float],
        fixture_goal_offsets: dict[int, tuple[float, float]],
        n_sims: int,
        seed: int | None,
    ) -> SimOutputs: ...


class M0Simulation:
    """Placeholder behind the frozen signature. Applies rating overrides to the
    base ratings; the M0 match model has no per-fixture hook, so goal offsets
    are accepted and ignored until the WS-A sim lands."""

    def __init__(self, fmt: FormatData, base_ratings: np.ndarray) -> None:
        self._fmt = fmt
        self._base = base_ratings

    def run_simulation(
        self,
        rating_overrides: dict[str, float],
        fixture_goal_offsets: dict[int, tuple[float, float]],
        n_sims: int,
        seed: int | None,
    ) -> SimOutputs:
        ratings = self._base.copy()
        index = self._fmt.team_index()
        for team_id, delta in rating_overrides.items():
            if team_id in index:
                ratings[index[team_id]] += delta
        result = run_tournament(self._fmt, ratings, n_sims=n_sims, seed=seed or 0)
        return SimOutputs(
            n_sims=n_sims,
            england=build_england(self._fmt, result),
            slots=build_slots(self._fmt, result),
        )
