from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.contracts import ForecastOutput, GraphPatch, NodePatch, ResearchOutput
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import GraphModels, run_graph


async def test_demand_submit_runs_after_hard_retries_exhausted(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.submission.validation_failures = settings.agent_submit_retries + 1

    demanded: list[str] = []

    def forced_submit(prompt: str) -> ForecastOutput:
        demanded.append(prompt)
        return ForecastOutput(summary="forced submit")

    models = GraphModels(
        master=scripted_model(
            [GraphPatch(ops=[NodePatch(node_id="research-1", kind="research", objective="r", brief="r")])]
        ),
        nodes={
            "research": scripted_model([ResearchOutput(summary="wave one")], model_name="research"),
            "quant": scripted_model([], model_name="unused"),
            "forecast": scripted_model([forced_submit]),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)
    deps.runtime.shutdown()

    assert demanded, "exhausted hard retries must not skip the final demand-submit"
    assert result.validation_failures == settings.agent_submit_retries + 1
