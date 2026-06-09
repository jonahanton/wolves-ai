from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


class ReadJournalArgs(BaseModel):
    run_id: str | None = None


async def _read_journal(args: ReadJournalArgs, deps: AgentDeps) -> ToolResult[Any]:
    text = deps.memory.read_journal(args.run_id) if args.run_id else deps.memory.read_latest_journal()
    return ToolResult(payload={"journal": text or "(no journal found)"})


SPEC = ToolSpec(
    name="read_journal",
    description="Read a previous run's journal. Leave run_id unset for the most recent one.",
    args_model=ReadJournalArgs,
    fn=_read_journal,
)
