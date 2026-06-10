from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from wolves.agent.deps import AgentDeps
from wolves.agent.scenarios import UnknownScenarioError
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


class ScenarioUpdateArgs(BaseModel):
    action: Literal["open", "reweight", "collapse", "expire", "carry"]
    scenario_id: str | None = None
    name: str | None = None
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str


async def _scenario_update(args: ScenarioUpdateArgs, deps: AgentDeps) -> ToolResult[Any]:
    registry = deps.scenarios
    if registry is None:
        return ToolResult(
            ok=False, payload=None, error=ToolError(type="no_registry", message="this run has no scenario registry")
        )
    run_id = deps.runtime.run_id
    if args.action == "open":
        if not args.name:
            return ToolResult(
                ok=False, payload=None, error=ToolError(type="invalid_arguments", message="open needs a name")
            )
        state = registry.open(name=args.name, run_id=run_id, weight=args.weight, reason=args.reason)
    else:
        if args.scenario_id is None:
            return ToolResult(
                ok=False, payload=None, error=ToolError(type="invalid_arguments", message="pass scenario_id")
            )
        status = {"reweight": "reweighted", "collapse": "collapsed", "expire": "expired", "carry": "open"}[args.action]
        try:
            state = registry.update(
                args.scenario_id, run_id=run_id, status=status, weight=args.weight, reason=args.reason
            )
        except UnknownScenarioError as exc:
            return ToolResult(ok=False, payload=None, error=ToolError(type="unknown_scenario", message=str(exc)))
    return ToolResult(payload=state.model_dump(mode="json", exclude={"history"}))


SPEC = ToolSpec(
    name="scenario_update",
    description=(
        "Maintain the cross-run scenario registry: open a named world with a cited weight, "
        "reweight or carry it on new evidence, collapse it when resolved, expire it when stale. "
        "Yesterday's open scenarios are in your dossier; resolving each one is part of today's "
        "argument."
    ),
    args_model=ScenarioUpdateArgs,
    fn=_scenario_update,
)
