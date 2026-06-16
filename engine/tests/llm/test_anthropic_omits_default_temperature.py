from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from wolves.llm.anthropic import AnthropicClient


@dataclass
class _Usage:
    input_tokens: int = 10
    output_tokens: int = 5
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class _Block:
    def __init__(
        self,
        *,
        btype: str,
        name: str | None = None,
        text: str = "",
        payload: dict[str, Any] | None = None,
    ):
        self.type = btype
        self.name = name
        self.text = text
        self.input = payload or {}

    def model_dump(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type}
        if self.name is not None:
            payload["name"] = self.name
        if self.text:
            payload["text"] = self.text
        if self.input:
            payload["input"] = self.input
        return payload


class _Message:
    def __init__(self, content: list[_Block]):
        self.id = "msg-test"
        self.content = content
        self.usage = _Usage()
        self.stop_reason = "end_turn"


class _Messages:
    def __init__(self) -> None:
        self.kwargs: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _Message:
        self.kwargs.append(kwargs)
        tools = kwargs.get("tools") or []
        schema_name = tools[0]["name"] if tools else "Forecast"
        return _Message([_Block(btype="tool_use", name=schema_name, payload={"ok": True})])


class _AsyncAnthropic:
    def __init__(self) -> None:
        self.messages = _Messages()

    async def close(self) -> None:
        return None


async def test_anthropic_adapter_omits_default_temperature():
    api = _AsyncAnthropic()
    client = AnthropicClient("claude-test", api_key="test", client=cast("Any", api))

    await client.complete(
        user="u",
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        schema_name="Forecast",
    )
    await client.complete_tools(messages=[{"role": "user", "content": "u"}], tools=[])

    assert all("temperature" not in kwargs for kwargs in api.messages.kwargs)


async def test_anthropic_adapter_sends_explicit_temperature():
    api = _AsyncAnthropic()
    client = AnthropicClient("claude-test", api_key="test", client=cast("Any", api))

    await client.complete(
        user="u",
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        schema_name="Forecast",
        temperature=0.2,
    )

    assert api.messages.kwargs[0]["temperature"] == 0.2
