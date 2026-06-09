from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from wolves.agent.contracts import LedgerStatus
from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult


class LedgerQueryArgs(BaseModel):
    team_id: str | None = None
    status: LedgerStatus | None = None
    fresh_on: str | None = None


async def _ledger_query(args: LedgerQueryArgs, deps: AgentDeps) -> ToolResult[Any]:
    fresh_on: date | None = None
    if args.fresh_on is not None:
        try:
            fresh_on = date.fromisoformat(args.fresh_on)
        except ValueError:
            return ToolResult(
                ok=False,
                payload=None,
                error=ToolError(type="invalid_arguments", message="fresh_on must be an ISO date"),
            )
    entries = deps.ledger.query(team_id=args.team_id, status=args.status, fresh_on=fresh_on)
    return ToolResult(payload={"entries": [e.model_dump(mode="json") for e in entries]})


SPEC = ToolSpec(
    name="ledger_query",
    description=(
        "Query the evidence ledger by team, status and freshness (fresh_on keeps entries unexpired "
        "on that ISO date). Use it to find citation ids before submitting."
    ),
    args_model=LedgerQueryArgs,
    fn=_ledger_query,
)
