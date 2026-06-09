from __future__ import annotations

from pathlib import Path

import pytest

from wolves.observability import CapExceeded, Caps, EventLog, InMemoryTracer, ObservedRuntime, build_runtime


def _runtime(tmp_path: Path, *, caps: Caps | None = None) -> ObservedRuntime:
    return build_runtime(run_id="test-run", tracer=InMemoryTracer(), caps=caps or Caps.small(), runs_root=tmp_path)


def test_observe_writes_span_and_jsonl(tmp_path: Path):
    runtime = _runtime(tmp_path)
    with runtime.observe(kind="demo", actor="actor", name="demo-span") as rec:
        rec.set_output({"ok": True})
        rec.note(summary="did the thing", value=7)
    runtime.shutdown()

    events = EventLog.read(runtime.paths.events)
    matching = [e for e in events if e.kind == "demo"]
    assert matching and matching[0].summary == "did the thing"
    assert matching[0].trace_id and matching[0].observation_id
    assert runtime.tracer.by_name("demo-span")


def test_external_action_requires_active_observation(tmp_path: Path):
    runtime = _runtime(tmp_path)
    with pytest.raises(RuntimeError):
        runtime.charge_llm()
    runtime.shutdown()


def test_caps_block_excess_calls(tmp_path: Path):
    runtime = _runtime(tmp_path, caps=Caps(max_search_calls=1))
    with runtime.observe(kind="node", actor="n"):
        runtime.charge_search()
        with pytest.raises(CapExceeded):
            runtime.charge_search()
    runtime.shutdown()


def test_failed_observation_records_error_and_reraises(tmp_path: Path):
    runtime = _runtime(tmp_path)
    with pytest.raises(ValueError, match="boom"), runtime.observe(kind="demo", actor="a"):
        raise ValueError("boom")
    runtime.shutdown()

    events = EventLog.read(runtime.paths.events)
    assert any("ValueError: boom" in str(e.payload.get("error", "")) for e in events)


def test_budget_snapshot_mirrors_consumption(tmp_path: Path):
    runtime = _runtime(tmp_path)
    with runtime.observe(kind="node", actor="n"):
        runtime.charge_llm()
        runtime.add_cost(1234)
    snap = runtime.snapshot()
    runtime.shutdown()
    assert snap.llm_calls == 1
    assert snap.cost_micros == 1234
