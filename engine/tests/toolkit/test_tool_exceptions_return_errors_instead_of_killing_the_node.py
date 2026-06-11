from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from wolves.toolkit.adapters.pydantic_ai import build_toolset
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class _Args(BaseModel):
    team: str


async def _explodes(args: _Args, deps: Any) -> ToolResult[Any]:
    raise KeyError(f"no parameters for team {args.team!r}")


SPEC = ToolSpec(name="explode", description="always raises", args_model=_Args, fn=_explodes)


async def test_a_raising_tool_surfaces_as_an_error_result():
    seen: list[str] = []

    def replay(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not seen:
            seen.append("called")
            return ModelResponse(parts=[ToolCallPart(tool_name="explode", args={"team": "England"})])
        return ModelResponse(parts=[TextPart("recovered")])

    agent: Agent[None, str] = Agent(toolsets=[build_toolset([SPEC])])
    result = await agent.run("go", model=FunctionModel(replay))

    assert result.output == "recovered"
    tool_returns = [
        p.content
        for m in result.all_messages()
        for p in getattr(m, "parts", [])
        if getattr(p, "tool_name", None) == "explode" and hasattr(p, "content")
    ]
    payload = json.loads(tool_returns[0])
    assert payload["ok"] is False
    assert payload["error"]["type"] == "KeyError"
