from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.deps import AgentDeps, TodoItem
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class TodoWriteArgs(BaseModel):
    todos: list[TodoItem] = Field(default_factory=list)


async def _todo_write(args: TodoWriteArgs, deps: AgentDeps) -> ToolResult[Any]:
    deps.todos[:] = args.todos
    return ToolResult(payload={"todos": [t.model_dump() for t in deps.todos]})


SPEC = ToolSpec(
    name="todo_write",
    description=(
        "Replace your working plan with an updated todo list (content + status per item). Write "
        "one at the start of any multi-step task, mark items in_progress and completed as you go, "
        "and revise when findings change the plan. The full list replaces the old one each call; "
        "it costs no budget."
    ),
    args_model=TodoWriteArgs,
    fn=_todo_write,
)
