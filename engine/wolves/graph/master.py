from __future__ import annotations

import logging

from pydantic_ai.models import Model

from wolves.config import Settings
from wolves.graph.agents import master_agent
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import GraphPatch, NodeKind, NodePatch

logger = logging.getLogger(__name__)


async def plan_wave(prompt: str, *, model: Model) -> GraphPatch:
    """One master planning turn over the blackboard summary."""
    result = await master_agent().run(prompt, model=model)
    return result.output


def _kind_cap(kind: NodeKind, settings: Settings) -> int:
    return {
        "research": settings.graph_max_research_nodes,
        "quant": settings.graph_max_quant_nodes,
        "forecast": settings.graph_max_forecast_nodes,
        "critic": settings.graph_max_critic_nodes,
    }[kind]


def admit(patch: GraphPatch, *, board: Blackboard, settings: Settings) -> tuple[list[NodePatch], list[str]]:
    """Trim a graph patch against hard caps and lineage rules; drops are
    returned for the blackboard so the master can react, never fatal."""
    admitted: list[NodePatch] = []
    drops: list[str] = []
    seen = {n.node_id for n in board.nodes}
    replaced = {n.node_id for n in board.nodes if n.replaced_by is not None}
    kind_counts: dict[NodeKind, int] = {}
    for node in board.nodes:
        kind_counts[node.kind] = kind_counts.get(node.kind, 0) + 1
    forecast_admitted = False

    def drop(op: NodePatch, why: str) -> None:
        drops.append(f"{op.node_id}: {why}")
        logger.warning("admission dropped %s: %s", op.node_id, why)

    for op in patch.ops:
        if op.node_id in seen:
            drop(op, "duplicate node_id; node ids are unique for the whole run, pick a fresh one")
            continue
        if op.node_id.startswith("runner-"):
            drop(op, "runner- ids are reserved")
            continue
        if op.replaces is not None and op.replaces not in seen:
            drop(op, f"replaces unknown node {op.replaces!r}")
            continue
        if op.replaces is not None and op.replaces in replaced:
            drop(op, f"node {op.replaces!r} was already superseded; re-brief the replacement instead")
            continue
        unknown = [a for a in op.input_artifact_ids if not board.artifacts.has(a)]
        if unknown:
            drop(op, f"unknown artifact ids {unknown}")
            continue
        if op.kind == "forecast" and forecast_admitted:
            drop(op, "one forecast node per wave")
            continue
        if kind_counts.get(op.kind, 0) >= _kind_cap(op.kind, settings):
            drop(op, f"{op.kind} node budget for the run is spent")
            continue
        forecast_admitted = forecast_admitted or op.kind == "forecast"
        seen.add(op.node_id)
        if op.replaces is not None:
            replaced.add(op.replaces)
        kind_counts[op.kind] = kind_counts.get(op.kind, 0) + 1
        admitted.append(op)

    remaining = max(0, settings.graph_max_nodes - len(board.nodes))
    cap = min(remaining, settings.graph_max_wave_workers)
    for over in admitted[cap:]:
        drop(over, "over node or wave worker cap")
    return admitted[:cap], drops
