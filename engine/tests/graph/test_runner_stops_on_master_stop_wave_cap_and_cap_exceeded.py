from __future__ import annotations

from pathlib import Path

from pydantic_ai.models import Model

from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.contracts import Brief, ForecastOutput, ResearchOutput, WavePlan
from wolves.graph.fakes import scripted_model
from wolves.graph.observed_model import ObservedModel
from wolves.graph.runner import GraphModels, run_graph
from wolves.observability import Caps


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(_env_file=None, runs_root=tmp_path, **overrides)


def _research_plan(node_id: str) -> WavePlan:
    return WavePlan(briefs=[Brief(node_id=node_id, kind="research", objective=node_id, brief="...")])


def _models(master: Model, *, research: Model | None = None, forecast: Model | None = None) -> GraphModels:
    return GraphModels(
        master=master,
        nodes={
            "research": research or scripted_model([], model_name="unused"),
            "quant": scripted_model([], model_name="unused"),
            "forecast": forecast or scripted_model([ForecastOutput(summary="no submission")]),
            "critic": scripted_model([], model_name="unused"),
        },
    )


async def test_master_stop_ends_planning_after_one_turn(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    # A one-step master script: a second planning turn would exhaust it and raise.
    models = _models(scripted_model([WavePlan(stop=True, reason="nothing to do")]))

    result = await run_graph(deps, as_of="2026-06-10", models=models)

    assert result.submission is None
    assert not result.budget_exhausted
    deps.runtime.shutdown()


async def test_wave_cap_bounds_planning_turns(tmp_path: Path):
    deps = build_graph_deps(tmp_path, settings=_settings(tmp_path, graph_max_waves=2))
    research = scripted_model(
        [ResearchOutput(summary="wave one"), ResearchOutput(summary="wave two")],
        model_name="research",
    )
    # Exactly two planning turns are scripted; a third would exhaust the master.
    models = _models(
        scripted_model([_research_plan("research-1"), _research_plan("research-2")]),
        research=research,
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)

    assert result.submission is None
    assert result.waves >= 2
    deps.runtime.shutdown()


async def test_cap_exceeded_during_planning_marks_budget_exhausted(tmp_path: Path):
    deps = build_graph_deps(tmp_path, caps=Caps(max_llm_calls=0))
    master = ObservedModel(scripted_model([WavePlan(stop=True)]), runtime=deps.runtime)
    # Node scripts are empty: dispatching any node, including the final
    # demand-to-submit forecast, would raise GraphScriptExhaustedError.
    models = _models(master, forecast=scripted_model([], model_name="unused"))

    result = await run_graph(deps, as_of="2026-06-10", models=models)

    assert result.budget_exhausted
    assert result.submission is None
    deps.runtime.shutdown()
