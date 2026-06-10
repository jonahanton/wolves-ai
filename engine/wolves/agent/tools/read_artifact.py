from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult


class ReadArtifactArgs(BaseModel):
    artifact_id: str


async def _read_artifact(args: ReadArtifactArgs, deps: AgentDeps) -> ToolResult[Any]:
    store = deps.artifacts
    if store is None:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(type="no_artifact_store", message="this run has no artifact store"),
        )
    artifact = store.get(args.artifact_id)
    if artifact is None:
        known = ", ".join(r.id for r in store.all()) or "(none yet)"
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(type="unknown_artifact", message=f"no artifact {args.artifact_id!r}; known ids: {known}"),
        )
    payload: dict[str, Any] = artifact.model_dump(mode="json")
    files = store.workspace_files(artifact.id)
    if files:
        payload["workspace_files"] = files
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="read_artifact",
    description=(
        "Open one artifact from this run by id: its full typed payload, plus its workspace file "
        "listing when the producing node left files behind (quant analyses do). Your brief lists "
        "the artifact ids you were given; the blackboard summary names everything else."
    ),
    args_model=ReadArtifactArgs,
    fn=_read_artifact,
)
