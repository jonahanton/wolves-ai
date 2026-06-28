"""The reserve-funded terminal demand-submit fires under budget pressure even with a tail it can no longer price.
Counterpart: test_demand_submit_fires_despite_unadjudicated_branch (an affordable, unpriced branch)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pydantic_ai.models import Model

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.config import Settings
from wolves.graph.contracts import ForecastOutput, GraphPatch, NodePatch, ResearchOutput
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import GraphModels, run_graph
from wolves.observability import Caps


def _tail() -> dict:
    return {
        "branch_id": "france-overcredit",
        "teams": ["france"],
        "hypothesis": "France is over-credited on reputation.",
        "support": "The structural move outruns the priced evidence.",
        "collapse_condition": "Collapse if the gap clears the noise floor.",
        "suggested_quant_question": "Re-price France against the longshot lens.",
    }


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


async def test_demand_submit_fires_despite_an_unaffordable_open_tail(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        runs_root=tmp_path,
        storage_mode="local",
        graph_referee_enabled=False,
        graph_forecast_reserve_usd=1.0,
        graph_forecast_reserve_llm_calls=0,
        graph_referee_reserve_usd=0.0,
        graph_referee_reserve_llm_calls=0,
        graph_followup_floor_usd=0.30,
    )
    store = build_run_store(tmp_path)
    store.add(
        kind="critique",
        created_by="critic-1",
        summary="pre-mortem",
        payload={"challenges": [], "tail_branches": [_tail()]},
    )
    deps = build_graph_deps(tmp_path, settings=settings, caps=Caps(max_cost_micros=2_000_000))
    deps = dataclasses.replace(deps, artifacts=store)
    # 200k of headroom above the 1.0 reserve: the open tail can never be priced, yet the reserve funds one forecast.
    deps.runtime.budget.cost_micros = 800_000

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
    assert demanded, "the open tail must not veto the reserve-funded demand-submit"
    deps.runtime.shutdown()
