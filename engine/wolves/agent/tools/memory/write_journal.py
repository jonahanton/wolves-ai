from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class WriteJournalArgs(BaseModel):
    text: str
    lessons: str | None = None


async def _write_journal(args: WriteJournalArgs, deps: AgentDeps) -> ToolResult[Any]:
    path = deps.memory.write_journal(args.text)
    if args.lessons:
        deps.memory.stage_lessons(args.lessons)
    deps.runtime.emit("journal", deps.actor, f"journal written ({len(args.text)} chars)", path=str(path))
    return ToolResult(payload={"written": True, "lessons_staged": bool(args.lessons)})


SPEC = ToolSpec(
    name="write_journal",
    description=(
        "Append to today's run journal: what you investigated, what moved, what to re-check tomorrow. "
        "Pass `lessons` only for durable cross-run learnings; it appends to the curated LESSONS.md."
    ),
    args_model=WriteJournalArgs,
    fn=_write_journal,
)
