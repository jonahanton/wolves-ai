from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.agent_tools._timeout import run_with_timeout
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


class GetResultsAndFixturesArgs(BaseModel):
    date: str | None = None


async def _get_results_and_fixtures(args: GetResultsAndFixturesArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    deps.runtime.charge_data_fetch()
    with deps.runtime.observe(kind="data_fetch", actor=deps.actor, name="get_results_and_fixtures") as rec:
        matches = await run_with_timeout(
            deps.fixtures.fixtures(date=args.date),
            tool_name="get_results_and_fixtures",
            timeout_seconds=deps.settings.tool_timeout_seconds,
        )
        rec.set_output({"matches": len(matches)})
        rec.note(summary=f"fixtures{f' on {args.date}' if args.date else ''}: {len(matches)} match(es)")
    return ToolResult(payload={"matches": [m.model_dump(mode="json") for m in matches]})


SPEC = ToolSpec(
    name="get_results_and_fixtures",
    description=(
        "Structured tournament state from API-Football: played results, live scores and upcoming fixtures. "
        "Pass a YYYY-MM-DD date to narrow to one day; calls are rate-limited, so batch by date."
    ),
    args_model=GetResultsAndFixturesArgs,
    fn=_get_results_and_fixtures,
)
