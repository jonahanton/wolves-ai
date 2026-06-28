"""A critic's analytical tail keeps branch coverage open until a quant node
prices it. On news-heavy days the run can spend down to where no follow-up wave
fits above the finalisation reserve yet the gate still sits above it: the
forecast is dropped, the demand-submit is skipped, and the run ends without
submitting while the reserve goes unspent. The gate must release the moment the
follow-up it demands can no longer be funded."""

from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.config import Settings
from wolves.graph.blackboard import Blackboard
from wolves.observability import Caps, InMemoryTracer, build_runtime


def _tail(branch_id: str) -> dict:
    return {
        "branch_id": branch_id,
        "teams": ["france"],
        "hypothesis": "France is over-credited on reputation.",
        "support": "The structural move outruns the priced evidence.",
        "collapse_condition": "Collapse if the gap clears the noise floor.",
        "suggested_quant_question": "Re-price France against the longshot lens.",
    }


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        runs_root=tmp_path,
        storage_mode="local",
        graph_forecast_reserve_usd=1.0,
        graph_forecast_reserve_llm_calls=0,
        graph_referee_reserve_usd=0.0,
        graph_referee_reserve_llm_calls=0,
        graph_followup_floor_usd=0.30,
    )


def _board(tmp_path: Path, settings: Settings, runtime) -> Blackboard:
    store = build_run_store(tmp_path)
    store.add(
        kind="critique",
        created_by="critic-1",
        summary="pre-mortem",
        payload={"challenges": [], "tail_branches": [_tail("france-overcredit")]},
    )
    return Blackboard(
        artifacts=store,
        ledger=EvidenceLedger(tmp_path / "ledger.jsonl"),
        runtime=runtime,
        settings=settings,
    )


def test_open_tail_gates_the_forecast_while_a_follow_up_is_affordable(tmp_path: Path):
    settings = _settings(tmp_path)
    runtime = build_runtime(
        run_id="gate", tracer=InMemoryTracer(), caps=Caps(max_cost_micros=2_000_000), runs_root=tmp_path
    )
    board = _board(tmp_path, settings, runtime)

    assert board.branch_follow_up_reason(settings) is not None


def test_open_tail_releases_the_forecast_once_no_follow_up_fits(tmp_path: Path):
    settings = _settings(tmp_path)
    runtime = build_runtime(
        run_id="gate", tracer=InMemoryTracer(), caps=Caps(max_cost_micros=2_000_000), runs_root=tmp_path
    )
    board = _board(tmp_path, settings, runtime)

    # 200k of headroom sits above the 1.0 reserve, less than a 0.30 follow-up
    # call: the reserve is still intact but no adjudication wave can run.
    runtime.budget.cost_micros = 800_000

    assert board.branch_follow_up_reason(settings) is None
