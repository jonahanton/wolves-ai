from __future__ import annotations

from typing import Any, cast

from wolves.agent.tools.retrieval.rank_relevance import _Rankings
from wolves.agent.tools.submission.referee import RefereeReport
from wolves.llm.anthropic import AnthropicClient
from wolves.llm.client import harden_schema


class _Messages:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
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

    for response_model in (RefereeReport, _Rankings):
        await client.complete(
            user="review",
            schema=harden_schema(response_model.model_json_schema()),
            schema_name=response_model.__name__,
        )

    referee_tool = api.messages.requests[0]["tools"][0]
    assert referee_tool["strict"] is True
    assert referee_tool["name"] == "RefereeReport"
    assert referee_tool["input_schema"]["required"] == [
        "approved",
        "summary",
        "issues",
        "suggested_master_brief",
    ]
    assert referee_tool["input_schema"]["$defs"]["RefereeIssue"]["additionalProperties"] is False

    ranking_tool = api.messages.requests[1]["tools"][0]
    assert ranking_tool["strict"] is True
    assert ranking_tool["name"] == "_Rankings"
    score_schema = ranking_tool["input_schema"]["$defs"]["_Ranking"]["properties"]["score"]
    assert "minimum" not in score_schema
    assert "maximum" not in score_schema
    assert score_schema["description"] == "{maximum: 1.0, minimum: 0.0}"
