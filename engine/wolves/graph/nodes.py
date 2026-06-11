from __future__ import annotations

import asyncio
import dataclasses

from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from wolves.agent.deps import AgentDeps
from wolves.config import Settings
from wolves.graph.agents import node_agent
from wolves.graph.artifacts import ArtifactKind, RunArtifactStore
from wolves.graph.contracts import Brief, NodeKind, NodeOutcome
from wolves.graph.observed_model import CACHE_SETTINGS, ObservedModel
from wolves.toolkit._budget_gate import BudgetGate

_ARTIFACT_KINDS: dict[NodeKind, ArtifactKind] = {
    "research": "evidence",
    "quant": "quant",
    "forecast": "draft_forecast",
    "critic": "critique",
}


def _kickoff(brief: Brief, store: RunArtifactStore) -> str:
    # References only: payloads stay out of the kickoff so an arbitrarily
    # large dossier cannot blow the node's context; read_artifact pulls them.
    parts = [f"Objective: {brief.objective}", "", brief.brief]
    records = [r for r in (store.record(a) for a in brief.input_artifact_ids) if r is not None]
    if records:
        parts.append("")
        parts.append("Input artifacts (open any with read_artifact):")
        for record in records:
            parts.append(f"- {record.id} ({record.kind}, by {record.created_by}): {record.summary}")
    return "\n".join(parts)


def _request_limit(kind: NodeKind, settings: Settings) -> int:
    # The forecast node's submit-validate-retry loop costs a request per tool
    # round; the first metered run proved one global limit starves it.
    return {
        "research": settings.graph_research_request_limit,
        "quant": settings.graph_quant_request_limit,
        "forecast": settings.graph_forecast_request_limit,
        "critic": settings.graph_critic_request_limit,
    }[kind]


def _tool_budget(kind: NodeKind, settings: Settings) -> int:
    return {
        "research": settings.graph_research_tool_budget,
        "quant": settings.graph_quant_tool_budget,
        "forecast": settings.graph_forecast_tool_budget,
        "critic": settings.graph_critic_tool_budget,
    }[kind]


def _timeout(kind: NodeKind, settings: Settings) -> int:
    # Quant nodes build and check models, not single expressions; their
    # budget is minutes while a critic pass stays tight.
    return {
        "research": settings.graph_research_timeout_s,
        "quant": settings.graph_quant_timeout_s,
        "forecast": settings.graph_forecast_timeout_s,
        "critic": settings.graph_critic_timeout_s,
    }[kind]


async def execute_brief(brief: Brief, *, deps: AgentDeps, store: RunArtifactStore, model: Model) -> NodeOutcome:
    """Run one worker node to a typed artifact. Total: every failure, including
    CapExceeded surfacing in whatever shape pydantic-ai wraps it, degrades to a
    failed outcome so the wave and the run carry on."""
    settings = deps.settings
    node_deps = dataclasses.replace(
        deps,
        actor=brief.node_id,
        gate=BudgetGate(_tool_budget(brief.kind, settings)),
        todos=[],
        python_calls=0,
    )
    if isinstance(model, ObservedModel):
        # Only the forecast node may spend the held-back reserve; every other
        # kind hits its ceiling early so the run always affords a submission.
        hold_back = 0 if brief.kind == "forecast" else int(settings.graph_forecast_reserve_usd * 1_000_000)
        model = ObservedModel(model.wrapped, runtime=deps.runtime, actor=brief.node_id, hold_back_micros=hold_back)
    try:
        result = await asyncio.wait_for(
            node_agent(brief.kind).run(
                _kickoff(brief, store),
                deps=node_deps,
                model=model,
                model_settings=CACHE_SETTINGS,
                usage_limits=UsageLimits(request_limit=_request_limit(brief.kind, settings)),
            ),
            timeout=_timeout(brief.kind, settings),
        )
    except Exception as exc:
        return NodeOutcome(node_id=brief.node_id, kind=brief.kind, ok=False, error=f"{type(exc).__name__}: {exc}")
    output = result.output
    workspace_prefix: str | None = None
    flags: list[str] = []
    if brief.kind == "quant":
        workspace = deps.quant.workspace(brief.node_id)
        workspace_prefix = f"runs/{store.run_id}/workspace/quant/{workspace.dir.name}"
        usage = workspace.read_usage()
        if sum(usage.values()) == 0:
            flags.append("quant_no_computation")
        elif usage.get("sims", 0) == 0:
            flags.append("quant_no_simulation")
    artifact = store.add(
        kind=_ARTIFACT_KINDS[brief.kind],
        created_by=brief.node_id,
        summary=output.summary,
        payload=output.model_dump(mode="json"),
        workspace_prefix=workspace_prefix,
    )
    return NodeOutcome(
        node_id=brief.node_id,
        kind=brief.kind,
        ok=True,
        artifact_ids=[artifact.id],
        requests=result.usage.requests,
        flags=flags,
    )
