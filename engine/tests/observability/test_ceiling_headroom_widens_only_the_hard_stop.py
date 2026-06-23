from __future__ import annotations

from pathlib import Path

import pytest

from wolves.observability import Caps, InMemoryTracer, build_runtime
from wolves.observability.runtime import CapExceeded


def test_headroom_is_available_only_to_finalisation_calls(tmp_path: Path):
    runtime = build_runtime(
        run_id="headroom",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=100_000, headroom_micros=50_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        reservation = runtime.charge_llm()
        runtime.add_cost(60_000, reservation=reservation)
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm()
        runtime.charge_llm(use_headroom=True)
    runtime.shutdown()


def test_headroom_still_stops_beyond_the_widened_ceiling(tmp_path: Path):
    runtime = build_runtime(
        run_id="headroom-stop",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=100_000, headroom_micros=50_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        reservation = runtime.charge_llm(use_headroom=True)
        runtime.add_cost(150_000, reservation=reservation)
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm(use_headroom=True)
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


def test_reservation_floor_is_included_before_call_admission(tmp_path: Path):
    runtime = build_runtime(
        run_id="reserved",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=400_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace(), pytest.raises(CapExceeded, match="max_cost_micros"):
        runtime.charge_llm(reservation_floor_micros=450_000)
    runtime.shutdown()


def test_call_holdback_is_enforced_at_admission(tmp_path: Path):
    runtime = build_runtime(
        run_id="call-reserve",
        tracer=InMemoryTracer(),
        caps=Caps(max_llm_calls=6, max_cost_micros=1_000_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        runtime.charge_llm(hold_back_calls=4)
        runtime.charge_llm(hold_back_calls=4)
        with pytest.raises(CapExceeded, match="max_llm_calls"):
            runtime.charge_llm(hold_back_calls=4)
        runtime.charge_llm()
    runtime.shutdown()


def test_estimated_call_cost_is_not_clipped_to_available_budget(tmp_path: Path):
    runtime = build_runtime(
        run_id="cost-reserve",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=500_000),
        runs_root=tmp_path,
    )
    with runtime.run_trace():
        runtime.charge_llm(reservation_estimate_micros=300_000)
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm(reservation_estimate_micros=300_000)
    runtime.shutdown()
