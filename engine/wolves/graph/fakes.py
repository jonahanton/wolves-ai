"""Scripted pydantic-ai FunctionModels driving the graph offline at $0."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

ToolCalls = Sequence[tuple[str, dict[str, Any]]]
ScriptStep = ToolCalls | BaseModel | Callable[[str], BaseModel]


class GraphScriptExhaustedError(RuntimeError):
    def __init__(self, model_name: str) -> None:
        super().__init__(f"scripted model {model_name!r} ran out of steps")
        self.model_name = model_name


def _latest_prompt(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            texts = [p.content for p in message.parts if hasattr(p, "content") and isinstance(p.content, str)]
            if texts:
                return "\n".join(texts)
    return ""


def scripted_model(steps: Sequence[ScriptStep], *, model_name: str = "scripted") -> FunctionModel:
    """Replay steps in order: tool-call rounds, then a final typed output.

    A BaseModel step is returned via the agent's output tool; a callable step
    receives the latest user prompt text and returns the BaseModel, so a
    scripted master can cite artifact ids it reads off the blackboard summary."""
    remaining: list[ScriptStep] = list(steps)

    def replay(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not remaining:
            raise GraphScriptExhaustedError(model_name)
        step = remaining.pop(0)
        if callable(step) and not isinstance(step, BaseModel):
            step = step(_latest_prompt(messages))
        if isinstance(step, BaseModel):
            output_tool = info.output_tools[0]
            return ModelResponse(parts=[ToolCallPart(tool_name=output_tool.name, args=step.model_dump(mode="json"))])
        parts = [ToolCallPart(tool_name=name, args=args) for name, args in step]
        return ModelResponse(parts=parts)

    return FunctionModel(replay, model_name=model_name)
