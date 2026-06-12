"""Market-implied reach probabilities: invert the de-vigged outright into
strengths, then simulate the bracket under them. The market prices only the
title; every stage below champion is what those prices imply through the
model's match mechanics, so the champion leg stays the market's own number."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pydantic import BaseModel

from wolves.markets.inverse import PROB_FLOOR, strengths_matching_outright
from wolves.sim.mc import run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_team_reach

if TYPE_CHECKING:
    from wolves.models.contracts import FittedState
    from wolves.sim.format import FormatData, PlayedResult

IMPLIED_SIMS = 20_000


class ImpliedReachPoint(BaseModel):
    date: str
    captured_at: str
    outright: dict[str, float]
    teams: dict[str, dict[str, float]]


class ImpliedReachSeries(BaseModel):
    points: list[ImpliedReachPoint]


def market_implied_reach(
    fmt: FormatData,
    state: FittedState,
    outright: dict[str, float],
    *,
    results: dict[int, PlayedResult] | None = None,
    seed: int = 0,
    n_sims: int = IMPLIED_SIMS,
) -> dict[str, dict[str, float]]:
    """Per-team reach probabilities whose simulated outright matches the market's."""
    filled = {t.id: max(outright.get(t.id, PROB_FLOOR), PROB_FLOOR) for t in fmt.teams}
    adjusted, _ = strengths_matching_outright(fmt, state, filled, seed=seed, n_sims=n_sims, results=results)
    engine = PoissonMatchEngine(fmt, replace(adjusted, covariance=None))
    result = run_tournament(fmt, engine, n_sims=n_sims, seed=seed, results=results)
    return build_team_reach(fmt, result)
