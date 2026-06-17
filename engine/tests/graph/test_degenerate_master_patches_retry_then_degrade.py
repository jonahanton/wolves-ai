from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from tests.graph.test_runner_stops_on_master_stop_wave_cap_and_cap_exceeded import _models
from wolves.config import Settings
from wolves.graph.contracts import GraphPatch
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import run_graph


async def test_degenerate_patches_are_retried_in_call_then_degrade_to_a_stop(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_master_output_retries=2)
    deps = build_graph_deps(tmp_path, settings=settings)
    # output_retries=2 allows 3 attempts per call; the validator bounces all
    # three, the exhausted turn gets one simplified retry of another three,
    # and only then does planning degrade to a stop.
    models = _models(scripted_model([GraphPatch() for _ in range(6)]))

    result = await run_graph(deps, as_of="2026-06-11", models=models)

    assert result.submission is None
    assert not result.budget_exhausted
    deps.runtime.shutdown()
