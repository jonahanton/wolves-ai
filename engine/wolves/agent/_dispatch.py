"""One assistant turn's tool dispatch, shared by master and researcher loops.

Truncation and the budget annotation are applied to tool result content here
rather than the system prompt, so prompt caching survives across turns."""

from __future__ import annotations

import asyncio
from typing import Any

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.adapters.anthropic import dispatch
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.llm.client import ToolTurn
from wolves.tools._truncation import truncate_result


async def dispatch_tool_uses(turn: ToolTurn, specs: list[ToolSpec], deps: AgentDeps) -> list[dict[str, Any]]:
    """Dispatch every tool_use block in the turn concurrently, returning the
    tool_result content blocks for the next user message."""

    async def annotate(spec: ToolSpec, args: Any, result: ToolResult) -> str:
        text = truncate_result(result.model_dump_json(), deps.settings.tool_result_max_chars)
        return f"{text}\n[budget: tool calls {deps.gate.used}/{deps.gate.limit}]"

    return list(
        await asyncio.gather(
            *(
                dispatch({"id": b.id, "name": b.name, "input": b.input}, specs, deps, after_result=annotate)
                for b in turn.tool_use_blocks
            )
        )
    )
