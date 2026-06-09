"""Budget-gate guard shared by every budgeted tool.

Free tools (run_python, ledger, journal, submit_forecast) never call this:
scratch reasoning and bookkeeping must not compete with external actions
for budget, per the FREE_TOOLS convention."""

from __future__ import annotations

from typing import Any

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.result import ToolError, ToolResult
from wolves.tools._budget_gate import budget_exhausted_message


def reserve_or_refuse(deps: AgentDeps) -> ToolResult[Any] | None:
    if deps.gate.try_reserve():
        return None
    return ToolResult(
        ok=False,
        payload=None,
        error=ToolError(type="budget_exhausted", message=budget_exhausted_message()),
    )
