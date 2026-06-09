"""Scripted fake LLM driving the loop offline: dev mode and tests, $0 spend."""

from __future__ import annotations

import itertools
import json
from typing import Any

from wolves.llm.client import LLMClient, LLMResponse, ToolTurn, ToolUseBlock

_ids = itertools.count(1)


class ScriptExhaustedError(RuntimeError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"scripted fake LLM ran out of {kind} responses")
        self.kind = kind


def tool_call_turn(*calls: tuple[str, dict[str, Any]], text: str = "") -> ToolTurn:
    """One scripted assistant turn invoking the given tools."""
    content: list[dict[str, Any]] = []
    blocks: list[ToolUseBlock] = []
    if text:
        content.append({"type": "text", "text": text})
    for name, tool_input in calls:
        block_id = f"toolu_{next(_ids):04d}"
        content.append({"type": "tool_use", "id": block_id, "name": name, "input": tool_input})
        blocks.append(ToolUseBlock(id=block_id, name=name, input=tool_input))
    return ToolTurn(
        content=content,
        text=text,
        stop_reason="tool_use",
        model="fake-model",
        provider="fake",
        tool_use_blocks=blocks,
        usage={"input": 500, "output": 120},
    )


def text_turn(text: str) -> ToolTurn:
    return ToolTurn(
        content=[{"type": "text", "text": text}],
        text=text,
        stop_reason="end_turn",
        model="fake-model",
        provider="fake",
        usage={"input": 500, "output": 60},
    )


class ScriptedLLM(LLMClient):
    """Replays scripted tool turns and structured responses in order."""

    provider = "fake"

    def __init__(
        self,
        *,
        turns: list[ToolTurn],
        structured: list[dict[str, Any]] | None = None,
        model: str = "fake-model",
    ) -> None:
        self.model = model
        self._turns = list(turns)
        self._structured = list(structured or [])
        self.tool_turn_count = 0
        self.structured_count = 0

    async def complete(
        self,
        *,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
        system: str | None = None,
        max_tokens: int = 900,
        temperature: float = 0.0,
    ) -> LLMResponse:
        if not self._structured:
            raise ScriptExhaustedError("structured")
        self.structured_count += 1
        data = self._structured.pop(0)
        return LLMResponse(
            data=data,
            text=json.dumps(data),
            model=self.model,
            provider=self.provider,
            usage={"input": 300, "output": 90},
        )

    async def complete_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> ToolTurn:
        if not self._turns:
            raise ScriptExhaustedError("tool turn")
        self.tool_turn_count += 1
        return self._turns.pop(0)
