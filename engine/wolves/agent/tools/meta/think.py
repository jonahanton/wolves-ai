from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class ThinkArgs(BaseModel):
    thought: str


async def _think(args: ThinkArgs, deps: AgentDeps) -> ToolResult[Any]:
    return ToolResult(payload={"noted": True})


SPEC = ToolSpec(
    name="think",
    description=(
        "Pause and reason in a scratchpad before acting. Use it after surprising tool output, "
        "before an irreversible step like submitting, or to lay out competing explanations and "
        "decide between them. The thought is recorded, never acted on; it costs no budget."
    ),
    args_model=ThinkArgs,
    fn=_think,
)
