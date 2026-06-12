from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.contracts import GraphPatch
from wolves.graph.fakes import scripted_model
from wolves.graph.master import plan_wave
from wolves.observability import EventLog


async def test_master_output_retry_knob_widens_in_call_retries(tmp_path: Path):
    # Wider than the default of 4: a hardcoded narrower budget would exhaust
    # the primary turn and emit a failure before the simplified retry rescued
    # the patch, so the no-failure assertion pins the knob threading.
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_master_output_retries=6)
    deps = build_graph_deps(tmp_path, settings=settings)
    # pydantic_ai output_retries=N allows N retries after the first attempt:
    # exactly six bounced empty patches still leave a seventh, valid attempt.
    model = scripted_model([*(GraphPatch() for _ in range(6)), GraphPatch(stop=True, reason="ok")])

    patch = await plan_wave("plan", board_summary="{}", model=model, settings=settings, runtime=deps.runtime)

    assert patch.stop
    assert patch.reason == "ok"
    deps.runtime.shutdown()
    events = EventLog.read(deps.runtime.paths.events)
    assert not any(e.kind == "master_output_failure" for e in events)
