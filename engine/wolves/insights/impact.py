"""Transplant engine-measured shifts onto the agent's published scale in log odds."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

STAGES = ("r32", "r16", "qf", "sf", "final", "champion")
PROB_FLOOR = 1e-4


def _logit(p: float) -> float:
    clamped = min(max(p, PROB_FLOOR), 1.0 - PROB_FLOOR)
    return math.log(clamped / (1.0 - clamped))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def shifted(base: float, leg_from: float, leg_to: float) -> float:
    """The base probability moved by the legs' log-odds shift."""
    return _sigmoid(_logit(base) + _logit(leg_to) - _logit(leg_from))


def stage_impacts(
    agent: Mapping[str, float],
    then: Mapping[str, float],
    now: Mapping[str, float],
    held: Mapping[str, float],
) -> dict[str, dict[str, float]]:
    """Per-stage estimates on the agent scale, split into results and in-game components.

    The then leg simulates under the agent run's own fitted state with the results it
    saw, so the results component carries both attribution channels (bracket and refit);
    the in-game component is the current scores held to full time on top.
    """
    impacts = {}
    for stage in STAGES:
        published = agent.get(stage)
        if published is None:
            continue
        p_results = shifted(published, then[stage], now[stage])
        p_est = shifted(p_results, now[stage], held[stage])
        impacts[stage] = {
            "agent": round(published, 4),
            "estimated": round(p_est, 4),
            "from_results_pp": round((p_results - published) * 100.0, 2),
            "from_ingame_pp": round((p_est - p_results) * 100.0, 2),
        }
    return impacts


def estimated_stages(
    agent: Mapping[str, float],
    then: Mapping[str, float],
    point: Mapping[str, float],
) -> dict[str, float]:
    """One series point: the agent scale shifted by the full then-to-point leg."""
    return {stage: round(shifted(agent[stage], then[stage], point[stage]), 4) for stage in STAGES if stage in agent}
