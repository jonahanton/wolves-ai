"""Transplant engine-measured shifts onto the agent's published scale in log odds."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

STAGES = ("r32", "r16", "qf", "sf", "final", "champion")
EXIT_STAGES = ("groups", "r32", "r16", "qf", "sf", "final", "champion")
PROB_FLOOR = 1e-4
DISPLAY_FLOOR_PP = 0.5


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
            "after_results": round(p_results, 4),
            "estimated": round(p_est, 4),
            "from_results_pp": round((p_results - published) * 100.0, 2),
            "from_ingame_pp": round((p_est - p_results) * 100.0, 2),
            "display_floor_pp": DISPLAY_FLOOR_PP,
        }
    return impacts


def exit_impacts(
    agent: Mapping[str, float],
    then: Mapping[str, float],
    now: Mapping[str, float],
    held: Mapping[str, float],
) -> dict[str, dict[str, float]]:
    """Exit-stage estimates derived from projected cumulative reach chains."""
    agent_exit = exit_distribution(agent)
    after_exit = exit_distribution(_shifted_stages(agent, then, now))
    estimated_exit = exit_distribution(_shifted_stages(agent, then, held))
    return {
        stage: {
            "agent": round(agent_exit[stage], 4),
            "after_results": round(after_exit[stage], 4),
            "estimated": round(estimated_exit[stage], 4),
            "from_results_pp": round((after_exit[stage] - agent_exit[stage]) * 100.0, 2),
            "from_ingame_pp": round((estimated_exit[stage] - after_exit[stage]) * 100.0, 2),
            "display_floor_pp": DISPLAY_FLOOR_PP,
        }
        for stage in EXIT_STAGES
    }


def exit_distribution(cumulative: Mapping[str, float]) -> dict[str, float]:
    projected = _project_cumulative(cumulative)
    values = [projected[stage] for stage in STAGES]
    return {
        "groups": 1.0 - values[0],
        "r32": values[0] - values[1],
        "r16": values[1] - values[2],
        "qf": values[2] - values[3],
        "sf": values[3] - values[4],
        "final": values[4] - values[5],
        "champion": values[5],
    }


def estimated_stages(
    agent: Mapping[str, float],
    then: Mapping[str, float],
    point: Mapping[str, float],
) -> dict[str, float]:
    """One series point: the agent scale shifted by the full then-to-point leg."""
    return {stage: round(shifted(agent[stage], then[stage], point[stage]), 4) for stage in STAGES if stage in agent}


def _shifted_stages(
    agent: Mapping[str, float],
    then: Mapping[str, float],
    target: Mapping[str, float],
) -> dict[str, float]:
    return {stage: shifted(agent[stage], then[stage], target[stage]) for stage in STAGES if stage in agent}


def _project_cumulative(cumulative: Mapping[str, float]) -> dict[str, float]:
    values = [min(max(float(cumulative.get(stage, 0.0)), 0.0), 1.0) for stage in STAGES]
    for i in range(len(values) - 2, -1, -1):
        values[i] = max(values[i], values[i + 1])
    return dict(zip(STAGES, values, strict=True))
