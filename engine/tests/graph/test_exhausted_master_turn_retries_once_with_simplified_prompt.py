from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from tests.graph.test_runner_stops_on_master_stop_wave_cap_and_cap_exceeded import _models
from wolves.config import Settings
from wolves.graph.contracts import GraphPatch
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import run_graph


async def test_exhausted_master_turn_retries_once_with_simplified_prompt(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_master_output_retries=2)
    deps = build_graph_deps(tmp_path, settings=settings)
    prompts: list[str] = []

    def recovered(prompt: str) -> GraphPatch:
        prompts.append(prompt)
        return GraphPatch(stop=True, reason="recovered")

    # output_retries=2 allows 3 attempts; three empties exhaust the primary
    # turn, then the simplified retry hits the callable.
    models = _models(scripted_model([*(GraphPatch() for _ in range(3)), recovered]))

    result = await run_graph(deps, as_of="2026-06-11", models=models)

    assert result.submission is None
    assert prompts and "previous planning turn failed output validation" in prompts[0]
    assert "Blackboard:" in prompts[0]
    assert "Produce today's forecast" not in prompts[0]
    deps.runtime.shutdown()
