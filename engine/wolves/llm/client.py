from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    data: dict[str, Any]
    text: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    response_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    reasoning: str | None = None
    cost_micros: int = 0


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolTurn:
    """One assistant turn of a multi-tool ReAct loop. ``content`` is the raw block
    list to echo back verbatim on the next call (incl. thinking blocks the API
    requires to be preserved); ``tool_use_blocks`` is the parsed subset to dispatch."""

    content: list[dict[str, Any]]
    text: str
    stop_reason: str
    model: str
    provider: str
    tool_use_blocks: list[ToolUseBlock] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    response_id: str | None = None
    reasoning: str | None = None
    cost_micros: int = 0


class LLMClient(ABC):
    """A structured-output LLM client. Returns validated-against-schema JSON."""

    provider: str
    model: str

    @abstractmethod
    async def complete(
        self,
        *,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
        system: str | None = None,
        max_tokens: int = 900,
        temperature: float | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def complete_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float | None = None,
    ) -> ToolTurn:
        """Run ONE assistant turn over a multi-turn message list with multiple
        tools offered under ``tool_choice: auto`` (model may call a tool or stop)."""

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None


def harden_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a JSON schema acceptable to strict structured-output APIs: every
    object forbids extra properties and lists all properties as required."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema
