from __future__ import annotations

import json
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from wolves.agent.tools.retrieval.rank_relevance import _RANKER, _Rankings
from wolves.agent.tools.submission.referee import _REFEREE, RefereeReport
from wolves.graph.anthropic import build_anthropic_model


async def _run_and_capture(agent: Any, payload: dict[str, Any]) -> tuple[Any, Any]:
    captured: list[Any] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        output_tool = info.output_tools[0]
        captured.append(output_tool)
        return ModelResponse(parts=[ToolCallPart(tool_name=output_tool.name, args=payload)])

    result = await agent.run("review", model=FunctionModel(respond))
    return result.output, captured[0]


async def _anthropic_request(agent: Any, model_name: str, payload: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        output_tool = body["tools"][0]
        return httpx.Response(
            200,
            json={
                "id": "msg-test",
                "type": "message",
                "role": "assistant",
                "model": model_name,
                "content": [{"type": "tool_use", "id": "toolu-test", "name": output_tool["name"], "input": payload}],
                "stop_reason": "tool_use",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    anthropic_client = AsyncAnthropic(api_key="test", http_client=http_client)
    model = build_anthropic_model(model_name, AnthropicProvider(anthropic_client=anthropic_client))
    try:
        result = await agent.run("review", model=model)
    finally:
        await anthropic_client.close()
    return result.output, requests[0]


async def test_referee_output_uses_its_strict_production_schema():
    output, tool = await _run_and_capture(
        _REFEREE,
        {"approved": True, "summary": "Ready.", "issues": [], "suggested_master_brief": ""},
    )

    assert isinstance(output, RefereeReport)
    assert tool.strict is True
    assert tool.parameters_json_schema["required"] == [
        "approved",
        "summary",
        "issues",
        "suggested_master_brief",
    ]


async def test_relevance_output_uses_its_strict_production_schema():
    output, tool = await _run_and_capture(
        _RANKER,
        {"rankings": [{"url": "https://example.com", "score": 0.8, "reason": "Relevant."}]},
    )

    assert isinstance(output, _Rankings)
    assert tool.strict is True
    score_schema = tool.parameters_json_schema["$defs"]["_Ranking"]["properties"]["score"]
    assert score_schema["minimum"] == 0.0
    assert score_schema["maximum"] == 1.0


async def test_opus_referee_request_sends_strict_schema_to_anthropic():
    result, request = await _anthropic_request(
        _REFEREE,
        "claude-opus-4-8",
        {"approved": True, "summary": "Ready.", "issues": [], "suggested_master_brief": ""},
    )

    assert result.approved is True
    assert request["tool_choice"]["type"] == "any"
    output_tool = request["tools"][0]
    assert output_tool["strict"] is True
    assert output_tool["input_schema"]["additionalProperties"] is False
    assert output_tool["input_schema"]["$defs"]["RefereeIssue"]["additionalProperties"] is False
    assert "default" not in json.dumps(output_tool["input_schema"])


async def test_haiku_relevance_request_preserves_score_guidance():
    result, request = await _anthropic_request(
        _RANKER,
        "claude-haiku-4-5",
        {"rankings": [{"url": "https://example.com", "score": 0.8, "reason": "Relevant."}]},
    )

    assert result.rankings[0].score == 0.8
    assert request["tool_choice"]["type"] == "any"
    output_tool = request["tools"][0]
    assert output_tool["strict"] is True
    score_schema = output_tool["input_schema"]["$defs"]["_Ranking"]["properties"]["score"]
    assert "minimum" not in score_schema
    assert "maximum" not in score_schema
    assert "minimum: 0.0" in score_schema["description"]
    assert "maximum: 1.0" in score_schema["description"]
