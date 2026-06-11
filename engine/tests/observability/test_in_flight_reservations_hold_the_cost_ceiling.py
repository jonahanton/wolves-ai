from __future__ import annotations

from pathlib import Path

import pytest

from wolves.observability import Caps, InMemoryTracer, build_runtime
from wolves.observability.runtime import CapExceeded


def test_unsettled_calls_count_against_the_ceiling(tmp_path: Path):
    runtime = build_runtime(
        run_id="reserve", tracer=InMemoryTracer(), caps=Caps(max_cost_micros=100_000), runs_root=tmp_path
    )
    with runtime.run_trace():
        first = runtime.charge_llm()
        runtime.charge_llm()
        # Two default 50k reservations are in flight; a third call would project past the ceiling.
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm()
        # Settling at the real (cheap) cost releases the reservation and readmits callers.
        runtime.add_cost(10_000, reservation=first)
        runtime.charge_llm()
    runtime.shutdown()
