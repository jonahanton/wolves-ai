"""Transplant engine-measured changes onto the agent's published scale.

The engine baseline and the agent's published numbers differ in level by
construction (agents publish unblended mixtures), so engine probabilities are
never shown as the agent's. The engine measures change instead: CRN-paired
simulations from one fitted state give three legs (results as the agent saw
them, results now, in-play scores held to full time), and each leg's log-odds
shift is applied to the agent's published probability. Components are read
sequentially: results first, then the in-game shift on top.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

STAGES = ("r32", "r16", "qf", "sf", "final", "champion")
PROB_CLAMP = 1e-4


def _logit(p: float) -> float:
    clamped = min(max(p, PROB_CLAMP), 1.0 - PROB_CLAMP)
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
    """Per-stage estimates on the agent scale, split into results and in-game components."""
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
