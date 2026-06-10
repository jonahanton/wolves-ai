from __future__ import annotations

from pathlib import Path

from pydantic_ai.models import Model

from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.contracts import ForecastOutput, GraphPatch, NodePatch, ResearchOutput
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import GraphModels, run_graph
from wolves.observability import Caps


def _models(master: Model, *, research: Model, forecast: Model) -> GraphModels:
    return GraphModels(
        master=master,
        nodes={
            "research": research,
            "quant": scripted_model([], model_name="unused"),
            "forecast": forecast,
            "critic": scripted_model([], model_name="unused"),
        },
    )


async def test_forecast_reserve_funds_demand_submit_when_budget_stops_waves(tmp_path: Path):
    settings = Settings(
        _env_file=None, runs_root=tmp_path, graph_forecast_reserve_usd=0.5, graph_forecast_reserve_llm_calls=0
    )
    deps = build_graph_deps(tmp_path, settings=settings, caps=Caps(max_cost_micros=1_000_000))
    # Spend crosses the reserve threshold (cap minus reserve) but not the cap itself.
    deps.runtime.budget.cost_micros = 600_000

    demanded: list[str] = []

    def forced_submit(prompt: str) -> ForecastOutput:
        demanded.append(prompt)
        return ForecastOutput(summary="forced submit")

    models = _models(
        scripted_model([GraphPatch(ops=[NodePatch(node_id="research-1", kind="research", objective="r", brief="r")])]),
        research=scripted_model([ResearchOutput(summary="wave one")], model_name="research"),
        forecast=scripted_model([forced_submit]),
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)

    assert result.budget_exhausted
    assert demanded, "the reserve must fund the final demand-submit forecast"
    deps.runtime.shutdown()
