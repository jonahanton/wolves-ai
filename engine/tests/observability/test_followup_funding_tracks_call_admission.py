"""can_fund_followup_call must flip false at the exact point charge_llm would
start rejecting an ordinary node's next call. A gap between the two would strand
a run in a budget dead zone: unable to fund a follow-up wave yet still gating the
forecast that the held-back reserve exists to fund."""

from __future__ import annotations

from pathlib import Path

from wolves.observability import Caps, InMemoryTracer, build_runtime


def _runtime(tmp_path: Path, caps: Caps):
    return build_runtime(run_id="fund", tracer=InMemoryTracer(), caps=caps, runs_root=tmp_path)


def test_funding_stops_one_reservation_before_the_held_back_reserve(tmp_path: Path):
    runtime = _runtime(tmp_path, Caps(max_cost_micros=2_000_000, max_llm_calls=100))

    runtime.budget.cost_micros = 700_000
    assert runtime.can_fund_followup_call(hold_back_micros=1_000_000, floor_micros=300_000)

    # Headroom above the reserve is now 200k, smaller than a 300k call: the next
    # call would be rejected, so funding must report false before the reserve is
    # touched.
    runtime.budget.cost_micros = 800_000
    assert not runtime.can_fund_followup_call(hold_back_micros=1_000_000, floor_micros=300_000)


def test_in_flight_reservations_count_against_funding(tmp_path: Path):
    runtime = _runtime(tmp_path, Caps(max_cost_micros=2_000_000, max_llm_calls=100))
    runtime.budget.cost_micros = 600_000
    runtime._in_flight_micros = 200_000

    assert not runtime.can_fund_followup_call(hold_back_micros=1_000_000, floor_micros=300_000)


def test_call_ceiling_stops_funding_within_the_reserve(tmp_path: Path):
    runtime = _runtime(tmp_path, Caps(max_cost_micros=0, max_llm_calls=10))
    runtime.budget.llm_calls = 8

    assert not runtime.can_fund_followup_call(hold_back_calls=4)
    runtime.budget.llm_calls = 5
    assert runtime.can_fund_followup_call(hold_back_calls=4)


def test_disabled_cost_ceiling_always_funds(tmp_path: Path):
    runtime = _runtime(tmp_path, Caps(max_cost_micros=0, max_llm_calls=100))
    runtime.budget.cost_micros = 9_000_000

    assert runtime.can_fund_followup_call(hold_back_micros=1_000_000, floor_micros=300_000)
