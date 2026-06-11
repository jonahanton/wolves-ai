from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from wolves.graph.observed_model import ObservedModel
from wolves.observability import CapExceeded, Caps, InMemoryTracer, build_runtime

# Default (sonnet) prices applied to the explicit usage mapping below:
# 1000*3 + 500*15 + 200*6 + 100*0.3 micro-dollars.
EXPECTED_COST_MICROS = 11_280


def _counting_inner() -> tuple[FunctionModel, list[int]]:
    invocations: list[int] = []

    def inner(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        invocations.append(1)
        return ModelResponse(
            parts=[TextPart("ok")],
            usage=RequestUsage(input_tokens=1000, output_tokens=500, cache_write_tokens=200, cache_read_tokens=100),
        )

    return FunctionModel(inner), invocations


async def test_charges_before_delegating_and_costs_all_token_classes(tmp_path: Path):
    runtime = build_runtime(
        run_id="om-run",
        tracer=InMemoryTracer(),
        caps=Caps(max_llm_calls=1, max_cost_micros=1_000_000),
        runs_root=tmp_path,
    )
    inner, invocations = _counting_inner()
    model = ObservedModel(inner, runtime=runtime)
    messages: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart("hi")])]

    with runtime.run_trace():
        response = await model.request(messages, None, ModelRequestParameters())
        assert response.parts
        assert len(invocations) == 1
        assert runtime.budget.llm_calls == 1
        assert runtime.budget.cost_micros == EXPECTED_COST_MICROS

        with pytest.raises(CapExceeded, match="max_llm_calls"):
            await model.request(messages, None, ModelRequestParameters())
        assert len(invocations) == 1
    runtime.shutdown()


async def test_refuses_outside_an_active_observation(tmp_path: Path):
    runtime = build_runtime(run_id="om-run-2", tracer=InMemoryTracer(), caps=Caps(), runs_root=tmp_path)
    inner, invocations = _counting_inner()
    model = ObservedModel(inner, runtime=runtime)

    with pytest.raises(RuntimeError, match="no active observation"):
        await model.request([ModelRequest(parts=[UserPromptPart("hi")])], None, ModelRequestParameters())
    assert not invocations
    runtime.shutdown()
