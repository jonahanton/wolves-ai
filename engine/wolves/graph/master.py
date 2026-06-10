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


def admit(plan: WavePlan, *, board: Blackboard, settings: Settings) -> tuple[list[Brief], list[str]]:
    """Trim a wave plan against hard caps; drops are returned for the
    blackboard so the master can react, never fatal."""
    admitted: list[Brief] = []
    drops: list[str] = []
    seen = {n.node_id for n in board.nodes}
    forecast_admitted = False

    def drop(brief: Brief, why: str) -> None:
        drops.append(f"{brief.node_id}: {why}")
        logger.warning("admission dropped %s: %s", brief.node_id, why)

    for brief in plan.briefs:
        if brief.node_id in seen:
            drop(brief, "duplicate node_id; node ids are unique for the whole run, pick a fresh one")
            continue
        if brief.node_id.startswith("runner-"):
            drop(brief, "runner- ids are reserved")
            continue
        unknown = [a for a in brief.input_artifact_ids if not board.artifacts.has(a)]
        if unknown:
            drop(brief, f"unknown artifact ids {unknown}")
            continue
        if brief.kind == "forecast" and forecast_admitted:
            drop(brief, "one forecast node per wave")
            continue
        forecast_admitted = forecast_admitted or brief.kind == "forecast"
        seen.add(brief.node_id)
        admitted.append(brief)

    remaining = max(0, settings.graph_max_nodes - len(board.nodes))
    cap = min(remaining, settings.graph_max_wave_workers)
    for over in admitted[cap:]:
        drop(over, "over node or wave worker cap")
    return admitted[:cap], drops
