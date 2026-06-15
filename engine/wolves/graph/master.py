from __future__ import annotations

import json
import logging
import re

from pydantic_ai import Agent, UnexpectedModelBehavior, capture_run_messages
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart
from pydantic_ai.models import Model

from wolves.config import Settings
from wolves.graph.agents import master_agent
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import GraphPatch, NodeKind, NodePatch
from wolves.graph.observed_model import CACHE_SETTINGS
from wolves.observability.runtime import ObservedRuntime

logger = logging.getLogger(__name__)

_RAW_OUTPUT_MAX_CHARS = 4000
_FOCUS_TEAM_RE = re.compile(r"\bfocus team is ([a-z][a-z0-9_-]*)", re.IGNORECASE)
_DATASET_MINING_RE = re.compile(r"\b(mine|mining|scan|trawl|search)\b")
_RESULT_REFIT_FORBID_RE = re.compile(r"\b(avoid|do not|don't|never|not|without)\b")
_MARKET_GAP_TERMS = ("market gap", "market-gap", "model-vs-market", "model vs market", "gaps")
_NAMED_DATASET_MECHANISMS = (
    "friendly",
    "stale",
    "squad",
    "altitude",
    "travel",
    "host",
    "sentiment",
    "longshot",
    "injury class",
    "availability class",
    "calibration",
)

_SIMPLIFIED_PREAMBLE = (
    "The previous planning turn failed output validation. Return a minimal valid GraphPatch: "
    "either ops for the next wave, or stop=true with a short reason."
)


def _raw_output(message: ModelMessage | None) -> str:
    if not isinstance(message, ModelResponse):
        return ""
    chunks = [part.args_as_json_str() for part in message.parts if isinstance(part, ToolCallPart)]
    return "\n".join(chunks)[:_RAW_OUTPUT_MAX_CHARS]


def _emit_output_retries(runtime: ObservedRuntime, messages: list[ModelMessage]) -> None:
    """Mirror in-call output retries to events.jsonl so a live failure is diagnosable after the fact."""
    for index, message in enumerate(messages):
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if not isinstance(part, RetryPromptPart):
                continue
            error = part.content if isinstance(part.content, str) else json.dumps(part.content, default=repr)
            raw = _raw_output(messages[index - 1] if index else None)
            logger.warning("master output failed validation; retrying in-call: %s", error)
            runtime.emit(
                "master_output_retry",
                "master",
                "master output failed validation; retried in-call",
                raw_output=raw,
                validation_error=error,
            )


def _emit_output_failure(
    runtime: ObservedRuntime, exc: UnexpectedModelBehavior, *, attempt: str, raw_output: str
) -> None:
    logger.warning("master %s planning turn exhausted output retries: %s", attempt, exc)
    runtime.emit(
        "master_output_failure",
        "master",
        f"master {attempt} planning turn exhausted output retries",
        attempt=attempt,
        error=str(exc),
        cause=repr(exc.__cause__) if exc.__cause__ is not None else None,
        raw_output=raw_output,
    )


async def _planning_turn(
    agent: Agent[None, GraphPatch], prompt: str, *, model: Model, runtime: ObservedRuntime, attempt: str
) -> GraphPatch:
    with capture_run_messages() as messages:
        try:
            result = await agent.run(prompt, model=model, model_settings=CACHE_SETTINGS)
        except UnexpectedModelBehavior as exc:
            # The final failing attempt never earns a retry prompt, so its raw
            # output only survives on the failure event.
            _emit_output_retries(runtime, messages)
            _emit_output_failure(
                runtime, exc, attempt=attempt, raw_output=_raw_output(messages[-1] if messages else None)
            )
            raise
    _emit_output_retries(runtime, messages)
    return result.output


async def plan_wave(
    prompt: str, *, board_summary: str, model: Model, settings: Settings, runtime: ObservedRuntime
) -> GraphPatch:
    """One master planning turn over the blackboard summary. An exhausted turn
    gets one fresh, simplified retry before planning degrades to a stop."""
    agent = master_agent(settings.graph_master_output_retries)
    try:
        return await _planning_turn(agent, prompt, model=model, runtime=runtime, attempt="primary")
    except UnexpectedModelBehavior:
        pass
    simplified = f"{_SIMPLIFIED_PREAMBLE}\n\nBlackboard:\n{board_summary}"
    try:
        return await _planning_turn(agent, simplified, model=model, runtime=runtime, attempt="simplified")
    except UnexpectedModelBehavior:
        return GraphPatch(stop=True, reason="master output failed validation twice; ending planning")


def _kind_cap(kind: NodeKind, settings: Settings) -> int:
    return {
        "research": settings.graph_max_research_nodes,
        "quant": settings.graph_max_quant_nodes,
        "forecast": settings.graph_max_forecast_nodes,
        "critic": settings.graph_max_critic_nodes,
    }[kind]


def _unsafe_result_refit_brief(op: NodePatch) -> bool:
    if op.kind != "quant":
        return False
    text = op.brief.lower()
    for match in re.finditer("update_from_result", text):
        window = text[max(0, match.start() - 80) : match.start()]
        if _RESULT_REFIT_FORBID_RE.search(window):
            continue
        return True
    return False


def _generic_dataset_gap_brief(op: NodePatch) -> bool:
    if op.kind != "quant":
        return False
    text = f"{op.objective} {op.brief}".lower()
    return (
        "dataset" in text
        and _DATASET_MINING_RE.search(text) is not None
        and any(term in text for term in _MARKET_GAP_TERMS)
        and not any(term in text for term in _NAMED_DATASET_MECHANISMS)
    )


def _focus_team_drift(text: str, settings: Settings) -> str | None:
    expected = settings.focus_team.lower()
    for match in _FOCUS_TEAM_RE.finditer(text):
        found = match.group(1).lower()
        if found != expected:
            return f"focus team drifted to {found}; focus team is {expected}"
    return None


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

    if focus_drift := _focus_team_drift(patch.reason, settings):
        logger.warning("admission dropped patch: %s", focus_drift)
        return [], [f"patch: {focus_drift}"]

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
        if focus_drift := _focus_team_drift(f"{op.objective} {op.brief}", settings):
            drop(op, focus_drift)
            continue
        if _unsafe_result_refit_brief(op):
            drop(
                op,
                "update_from_result is for separately justified posterior strength updates, "
                "not applying played results",
            )
            continue
        if _generic_dataset_gap_brief(op):
            drop(op, "generic dataset mining for market gaps is too broad; name the mechanism to test")
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
