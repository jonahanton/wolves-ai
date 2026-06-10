from __future__ import annotations

import logging

from pydantic_ai.models import Model

from wolves.config import Settings
from wolves.graph.agents import master_agent
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import Brief, WavePlan

logger = logging.getLogger(__name__)


async def plan_wave(prompt: str, *, model: Model) -> WavePlan:
    """One master planning turn over the blackboard summary."""
    result = await master_agent().run(prompt, model=model)
    return result.output


def admit(plan: WavePlan, *, board: Blackboard, settings: Settings) -> list[Brief]:
    """Trim a wave plan against hard caps; every drop is logged, never fatal."""
    admitted: list[Brief] = []
    seen = {n.node_id for n in board.nodes}
    forecast_admitted = False

    for brief in plan.briefs:
        if brief.node_id in seen:
            logger.warning("admission dropped %s: duplicate node_id", brief.node_id)
            continue
        unknown = [a for a in brief.input_artifact_ids if not board.artifacts.has(a)]
        if unknown:
            logger.warning("admission dropped %s: unknown artifact ids %s", brief.node_id, unknown)
            continue
        if brief.kind == "forecast" and forecast_admitted:
            logger.warning("admission dropped %s: one forecast node per wave", brief.node_id)
            continue
        forecast_admitted = forecast_admitted or brief.kind == "forecast"
        seen.add(brief.node_id)
        admitted.append(brief)

    remaining = max(0, settings.graph_max_nodes - len(board.nodes))
    cap = min(remaining, settings.graph_max_wave_workers)
    for dropped in admitted[cap:]:
        logger.warning("admission dropped %s: over node or wave worker cap", dropped.node_id)
    return admitted[:cap]
