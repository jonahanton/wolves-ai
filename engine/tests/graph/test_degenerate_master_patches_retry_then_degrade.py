from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from tests.graph.test_runner_stops_on_master_stop_wave_cap_and_cap_exceeded import _models
from wolves.graph.contracts import GraphPatch
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import run_graph


async def test_degenerate_patches_are_retried_in_call_then_degrade_to_a_stop(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    # Validator bounces two empty patches; the third degrades to a stop.
    models = _models(scripted_model([GraphPatch(), GraphPatch(), GraphPatch()]))

    result = await run_graph(deps, as_of="2026-06-11", models=models)

    assert result.submission is None
    assert not result.budget_exhausted
    deps.runtime.shutdown()
