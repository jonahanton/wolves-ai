from __future__ import annotations

from pathlib import Path

import pytest

from wolves.observability import Caps, InMemoryTracer, build_runtime
from wolves.observability.runtime import CapExceeded


def test_headroom_admits_calls_between_ceiling_and_ceiling_plus_headroom(tmp_path: Path):
    runtime = build_runtime(
        run_id="headroom",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=100_000, headroom_micros=50_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        # Settle spend just past the advertised ceiling; without headroom this would block.
        reservation = runtime.charge_llm()
        runtime.add_cost(120_000, reservation=reservation)
        # Still inside the headroom band (120k < 150k), so a further call is admitted.
        runtime.charge_llm()
    runtime.shutdown()


def test_headroom_still_stops_beyond_the_widened_ceiling(tmp_path: Path):
    runtime = build_runtime(
        run_id="headroom-stop",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=100_000, headroom_micros=50_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        reservation = runtime.charge_llm()
        runtime.add_cost(150_000, reservation=reservation)
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm()
    runtime.shutdown()


def test_zero_headroom_keeps_the_hard_stop_at_the_ceiling(tmp_path: Path):
    runtime = build_runtime(
        run_id="no-headroom",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=100_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        reservation = runtime.charge_llm()
        runtime.add_cost(100_000, reservation=reservation)
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm()
    runtime.shutdown()
