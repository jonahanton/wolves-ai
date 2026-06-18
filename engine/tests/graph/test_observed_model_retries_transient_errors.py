from __future__ import annotations

import asyncio

import anthropic
import httpx
import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from wolves.graph.observed_model import ObservedModel, RetryPolicy, TransientLLMError
from wolves.observability import Caps, InMemoryTracer, build_runtime

MESSAGES: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart("hi")])]
FAST_RETRY = RetryPolicy(max_retries=2, base_delay_s=0.0, max_delay_s=0.0)


def _overloaded() -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(529, request=request)
    return anthropic.APIStatusError("overloaded", response=response, body=None)


def _flaky(fail_times: int, error: BaseException):
    calls = {"n": 0}

    def inner(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise error
        return ModelResponse(parts=[TextPart("ok")], usage=RequestUsage(input_tokens=1, output_tokens=1))

    return inner, calls


async def test_transient_error_is_retried_then_succeeds(tmp_path):
    runtime = build_runtime(run_id="om-retry", tracer=InMemoryTracer(), caps=Caps(), runs_root=tmp_path)
    inner, calls = _flaky(1, _overloaded())
    model = ObservedModel(FunctionModel(inner), runtime=runtime, retry=FAST_RETRY)
    with runtime.run_trace():
        response = await model.request(MESSAGES, None, ModelRequestParameters())
    assert response.parts
    assert calls["n"] == 2
    runtime.shutdown()


async def test_exhausted_transient_retries_raise_typed_error(tmp_path):
    runtime = build_runtime(run_id="om-exhaust", tracer=InMemoryTracer(), caps=Caps(), runs_root=tmp_path)
    inner, calls = _flaky(99, _overloaded())
    model = ObservedModel(FunctionModel(inner), runtime=runtime, retry=FAST_RETRY)
    with runtime.run_trace(), pytest.raises(TransientLLMError):
        await model.request(MESSAGES, None, ModelRequestParameters())
    assert calls["n"] == 3
    runtime.shutdown()


async def test_cancelled_error_is_never_retried(tmp_path):
    runtime = build_runtime(run_id="om-cancel", tracer=InMemoryTracer(), caps=Caps(), runs_root=tmp_path)
    inner, calls = _flaky(99, asyncio.CancelledError())
    model = ObservedModel(FunctionModel(inner), runtime=runtime, retry=FAST_RETRY)
    with runtime.run_trace(), pytest.raises(asyncio.CancelledError):
        await model.request(MESSAGES, None, ModelRequestParameters())
    assert calls["n"] == 1
    runtime.shutdown()
