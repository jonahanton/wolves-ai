from __future__ import annotations

from pathlib import Path

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from tests.graph.conftest import build_graph_deps
from wolves.graph.artifacts import ArtifactStore
from wolves.graph.contracts import Brief, ForecastOutput, ResearchOutput, WavePlan
from wolves.graph.fakes import scripted_model
from wolves.graph.nodes import execute_brief
from wolves.graph.runner import GraphModels, run_graph

GOOD_OUTPUT = ResearchOutput(summary="solid finding")


def _flaky_research() -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = str(messages[0].parts[-1].content)
        if "FAIL" in prompt:
            raise RuntimeError("scripted node failure")
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=GOOD_OUTPUT.model_dump())])

    return FunctionModel(respond)


async def test_execute_brief_is_total(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    brief = Brief(node_id="research-bad", kind="research", objective="FAIL", brief="FAIL")

    with deps.runtime.run_trace():
        outcome = await execute_brief(brief, deps=deps, store=store, model=_flaky_research())

    assert not outcome.ok
    assert outcome.error is not None and "RuntimeError" in outcome.error
    assert outcome.artifact_ids == []
    deps.runtime.shutdown()


async def test_wave_with_a_failed_node_still_merges_the_good_one(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    plan = WavePlan(
        briefs=[
            Brief(node_id="research-bad", kind="research", objective="FAIL", brief="FAIL"),
            Brief(node_id="research-good", kind="research", objective="good", brief="find things"),
        ]
    )
    models = GraphModels(
        master=scripted_model([plan, WavePlan(stop=True, reason="done")]),
        nodes={
            "research": _flaky_research(),
            "quant": scripted_model([], model_name="unused"),
            "forecast": scripted_model([ForecastOutput(summary="no submission")]),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)

    assert result.submission is None
    assert result.waves >= 1
    artifacts = list((deps.runtime.paths.root / "artifacts").glob("evidence-*.json"))
    assert len(artifacts) == 1
    deps.runtime.shutdown()
