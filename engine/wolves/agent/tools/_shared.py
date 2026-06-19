"""Budget-gate guard shared by every budgeted tool.

Free tools never call this: scratch reasoning, bookkeeping and workspace
computation must not compete with external actions for budget."""

from __future__ import annotations

from typing import Any

from wolves.agent.deps import AgentDeps
from wolves.toolkit._budget_gate import budget_exhausted_message
from wolves.toolkit.result import ToolError, ToolResult


def reserve_or_refuse(deps: AgentDeps, *, keep_free: int = 0) -> ToolResult[Any] | None:
    if deps.gate.try_reserve(keep_free=keep_free):
        return None
    return ToolResult(
        ok=False,
        payload=None,
        error=ToolError(type="budget_exhausted", message=budget_exhausted_message()),
    )


def forecaster_or_refuse(deps: AgentDeps) -> ToolResult[Any] | None:
    if deps.forecaster is not None:
        return None
    return ToolResult(
        ok=False,
        payload=None,
        error=ToolError(type="no_forecaster", message="this run carries no fitted forecaster"),
    )
