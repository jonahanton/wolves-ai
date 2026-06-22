from __future__ import annotations

from typing import Any, cast

from wolves.llm.anthropic import AnthropicClient


class _Messages:
    def __init__(self) -> None:
        self.request: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        tool = kwargs["tools"][0]
        block = type("ToolUse", (), {"type": "tool_use", "name": tool["name"], "input": {"approved": True}})()
        usage = type("Usage", (), {"input_tokens": 1, "output_tokens": 1})()
        return type("Message", (), {"id": "msg-test", "content": [block], "usage": usage})()


class _AsyncAnthropic:
    def __init__(self) -> None:
        self.messages = _Messages()

    async def close(self) -> None:
        return None


async def test_anthropic_structured_output_uses_strict_schema():
    api = _AsyncAnthropic()
    client = AnthropicClient("claude-test", api_key="test", client=cast("Any", api))

    await client.complete(
        user="review",
        schema={
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["approved", "confidence"],
            "additionalProperties": False,
        },
        schema_name="RefereeReport",
    )

    assert api.messages.request["tools"] == [
        {
            "name": "RefereeReport",
            "description": "Return the requested structured output.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "approved": {"type": "boolean"},
                    "confidence": {"type": "number", "description": "{minimum: 0.0, maximum: 1.0}"},
                },
                "required": ["approved", "confidence"],
                "additionalProperties": False,
            },
        }
    ]
