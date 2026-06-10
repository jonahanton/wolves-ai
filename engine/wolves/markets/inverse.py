"""Leitner-Hornik-Zeileis inverse tournament simulation: find strength offsets
under which the simulated outright matches the market's de-vigged outright.
Common random numbers (one fixed seed across iterations) make it deterministic."""

from __future__ import annotations

import logging
from dataclasses import replace

import numpy as np

from wolves.data.teams import registry_team_key
from wolves.models.contracts import FittedState
from wolves.sim.format import FormatData
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine

logger = logging.getLogger(__name__)

ITERATIONS = 40
# Title probability moves several log units per unit strength, so the
# fixed-point step must stay well below the inverse elasticity to converge.
STEP = 0.12
TOLERANCE = 0.02
PROB_FLOOR = 1e-4


class OutrightCoverageError(Exception):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"market outright has no probability for team(s) {missing}")


def title_probabilities(fmt: FormatData, state: FittedState, *, seed: int, n_sims: int) -> dict[str, float]:
    """Simulated championship probability per app team id, without parameter noise."""
    engine = PoissonMatchEngine(fmt, replace(state, covariance=None))
    result = run_tournament(fmt, engine, n_sims=n_sims, seed=seed)
    winners = result.ko_winner[max(result.ko_winner)]
    return {team.id: float((winners == i).mean()) for i, team in enumerate(fmt.teams)}


def strengths_matching_outright(
    fmt: FormatData,
    state: FittedState,
    market_outright: dict[str, float],
    *,
    seed: int,
    n_sims: int = 20_000,
    iterations: int = ITERATIONS,
) -> tuple[FittedState, dict[str, float]]:
    """Return (adjusted state, per-team strength offsets) whose simulated
    outright reproduces the market's."""
    missing = sorted(t.id for t in fmt.teams if t.id not in market_outright)
    if missing:
        raise OutrightCoverageError(missing)

    state_index = {team: i for i, team in enumerate(state.teams)}
    param_idx = np.array([state_index[registry_team_key(t.id)] for t in fmt.teams], dtype=np.intp)
    target = np.array([max(market_outright[t.id], PROB_FLOOR) for t in fmt.teams])
    target = target / target.sum()

    adjusted = state
    offsets = np.zeros(len(fmt.teams))
    for iteration in range(iterations):
        sim = title_probabilities(fmt, adjusted, seed=seed, n_sims=n_sims)
        sim_probs = np.maximum(np.array([sim[t.id] for t in fmt.teams]), PROB_FLOOR)
        gap = np.log(target) - np.log(sim_probs)
        if float(np.abs(gap).max()) < TOLERANCE:
            logger.debug("inverse simulation converged after %d iterations", iteration)
            break
        offsets += STEP * gap
        strengths = state.strengths.copy()
        strengths[param_idx] += offsets
        adjusted = replace(state, strengths=strengths)
    return adjusted, {team.id: float(offsets[i]) for i, team in enumerate(fmt.teams)}
