from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from tests.graph.test_runner_stops_on_master_stop_wave_cap_and_cap_exceeded import _models
from wolves.config import Settings
from wolves.graph.contracts import GraphPatch
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import run_graph
from wolves.observability import EventLog


async def test_master_output_failures_land_in_events_with_raw_output(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_master_output_retries=1)
    deps = build_graph_deps(tmp_path, settings=settings)
    # output_retries=1 allows 2 attempts per call; both the primary turn and
    # the simplified retry exhaust, so the wave degrades to a stop and the
    # demand-submit safety net still runs.
    models = _models(scripted_model([GraphPatch() for _ in range(4)]))

    result = await run_graph(deps, as_of="2026-06-11", models=models)

    assert result.submission is None
    assert not result.budget_exhausted
    deps.runtime.shutdown()

    events = EventLog.read(deps.runtime.paths.events)
    retries = [e for e in events if e.kind == "master_output_retry"]
    failures = [e for e in events if e.kind == "master_output_failure"]
    assert len(retries) == 2
    for event in retries:
        assert '"ops":[]' in event.payload["raw_output"]
        assert "Empty patch" in event.payload["validation_error"]
    assert [e.payload["attempt"] for e in failures] == ["primary", "simplified"]
    for event in failures:
        assert "Exceeded maximum output retries" in event.payload["error"]
        assert "ModelRetry" in event.payload["cause"]
        assert '"ops":[]' in event.payload["raw_output"]
    # The demand-submit forecast node still produced an outcome.
    assert any(e.kind == "node" and e.actor == "runner-demand-submit" for e in events)
