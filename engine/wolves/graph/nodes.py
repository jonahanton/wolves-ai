from __future__ import annotations

import asyncio
import dataclasses
import json

from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from wolves.agent.deps import AgentDeps
from wolves.graph.agents import node_agent
from wolves.graph.artifacts import ArtifactKind, ArtifactStore
from wolves.graph.contracts import Brief, NodeKind, NodeOutcome
from wolves.tools._budget_gate import BudgetGate

_ARTIFACT_KINDS: dict[NodeKind, ArtifactKind] = {
    "research": "evidence",
    "quant": "quant",
    "forecast": "draft_forecast",
    "critic": "critique",
}


def _kickoff(brief: Brief, store: ArtifactStore) -> str:
    parts = [f"Objective: {brief.objective}", "", brief.brief]
    for artifact_id in brief.input_artifact_ids:
        artifact = store.get(artifact_id)
        if artifact is None:
            continue
        parts.append("")
        parts.append(f"Artifact {artifact.id} ({artifact.kind}, by {artifact.created_by}):")
        parts.append(json.dumps(artifact.payload, ensure_ascii=False))
    return "\n".join(parts)


async def execute_brief(brief: Brief, *, deps: AgentDeps, store: ArtifactStore, model: Model) -> NodeOutcome:
    """Run one worker node to a typed artifact. Total: every failure, including
    CapExceeded surfacing in whatever shape pydantic-ai wraps it, degrades to a
    failed outcome so the wave and the run carry on."""
    node_deps = dataclasses.replace(deps, actor=brief.node_id, gate=BudgetGate(), python_calls=0)
    settings = deps.settings
    try:
        result = await asyncio.wait_for(
            node_agent(brief.kind).run(
                _kickoff(brief, store),
                deps=node_deps,
                model=model,
                usage_limits=UsageLimits(request_limit=settings.graph_node_request_limit),
            ),
            timeout=settings.graph_node_timeout_s,
        )
    except Exception as exc:
        return NodeOutcome(node_id=brief.node_id, kind=brief.kind, ok=False, error=f"{type(exc).__name__}: {exc}")
    output = result.output
    artifact = store.add(
        kind=_ARTIFACT_KINDS[brief.kind],
        created_by=brief.node_id,
        summary=output.summary,
        payload=output.model_dump(mode="json"),
    )
    return NodeOutcome(node_id=brief.node_id, kind=brief.kind, ok=True, artifact_ids=[artifact.id])
