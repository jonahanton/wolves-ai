from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.contracts import LedgerStatus
from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


class LedgerAppendArgs(BaseModel):
    claim: str
    source_url: str
    status: LedgerStatus
    mechanism: str
    proposed_delta: float = 0.0
    expiry: str | None = None
    team_id: str | None = None


async def _ledger_append(args: LedgerAppendArgs, deps: AgentDeps) -> ToolResult[Any]:
    entry = deps.ledger.append(
        claim=args.claim,
        source_url=args.source_url,
        status=args.status,
        mechanism=args.mechanism,
        proposed_delta=args.proposed_delta,
        expiry=args.expiry,
        team_id=args.team_id,
    )
    deps.runtime.emit("ledger", deps.actor, f"ledger {entry.id}: {args.status} {args.claim[:80]}", entry_id=entry.id)
    return ToolResult(payload={"id": entry.id})


SPEC = ToolSpec(
    name="ledger_append",
    description=(
        "Record one load-bearing claim in the append-only evidence ledger: the claim, its source URL, "
        "status (confirmed, probable or rumour), the mechanism by which it moves a rating, the proposed "
        "Elo delta, an expiry date and the team it concerns. Every rating override in your final submission "
        "must cite ledger entry ids, and rumours can never justify a nonzero delta."
    ),
    args_model=LedgerAppendArgs,
    fn=_ledger_append,
)
