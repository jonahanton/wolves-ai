from __future__ import annotations

from typing import Any

from wolves.agent.contracts import WorkerResult
from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


async def _report_findings(args: WorkerResult, deps: AgentDeps) -> ToolResult[Any]:
    deps.worker_reports.append(args)
    return ToolResult(payload={"reported": True})


SPEC = ToolSpec(
    name="report_findings",
    description=(
        "Report your findings back to the master agent. This is the only way to finish your task: "
        "a one-paragraph summary, concrete evidence items each with a claim, source URL and exact quote, "
        "and signals for anything missing or worth following up."
    ),
    args_model=WorkerResult,
    fn=_report_findings,
)
