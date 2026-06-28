"""At dead-zone spend an ordinary node holding back the full reserve is capped, while the final
forecast, holding back only the referee slice and drawing on headroom, is still funded."""

from __future__ import annotations

from pathlib import Path

import pytest

from wolves.observability import Caps, InMemoryTracer, build_runtime
from wolves.observability.runtime import CapExceeded


def test_reserve_and_headroom_fund_the_final_forecast(tmp_path: Path):
    runtime = build_runtime(
        run_id="finalise",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=2_000_000, headroom_micros=2_000_000, max_llm_calls=100),
        runs_root=tmp_path,
    )
    forecast_reserve, referee_reserve = 1_000_000, 0
    runtime.budget.cost_micros = 1_900_000

    with runtime.run_trace():
        with pytest.raises(CapExceeded):
            runtime.charge_llm(hold_back_micros=forecast_reserve + referee_reserve)
        runtime.charge_llm(hold_back_micros=referee_reserve, use_headroom=True)

    runtime.shutdown()
