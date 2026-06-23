from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from wolves.graph.observed_model import ObservedModel
from wolves.observability import Caps, InMemoryTracer, build_runtime

MESSAGES: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart("hi")])]


def _boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise RuntimeError("upstream 500")


def _ok(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart("ok")], usage=RequestUsage(input_tokens=10, output_tokens=10))


async def test_failed_request_releases_the_reservation(tmp_path: Path):
    runtime = build_runtime(
        run_id="om-fail", tracer=InMemoryTracer(), caps=Caps(max_cost_micros=100_000), runs_root=tmp_path
    )

    with runtime.run_trace():
        with pytest.raises(RuntimeError, match="upstream 500"):
            await ObservedModel(FunctionModel(_boom), runtime=runtime).request(MESSAGES, None, ModelRequestParameters())
        response = await ObservedModel(FunctionModel(_ok), runtime=runtime).request(
            MESSAGES, None, ModelRequestParameters()
        )
        assert response.parts
    runtime.shutdown()
