"""End-to-end offline proof of the harness: a scripted FakeLLM drives the
master loop through search, ledger, sim and submission; the validator rejects
an invalid submission, the tripwire injects an explain-or-revise turn, the
valid resubmission passes, and the K-sample median plus event log all work."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_submission
from wolves.agent.deps import AgentDeps
from wolves.agent.fakes import ScriptedLLM, tool_call_turn
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.loop import run_master
from wolves.agent.memory import RunMemory
from wolves.agent.sim_runner import EngineSimulation
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FakeFixturesClient
from wolves.clients.odds import FakeOddsClient
from wolves.config import Settings
from wolves.connectors import FakeFetchClient, FakeSearchClient, ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability import Caps, EventLog, InMemoryTracer, build_runtime
from wolves.quant.observed import ObservedQuant
from wolves.tools._budget_gate import BudgetGate

INVALID = build_submission(
    narrative=build_submission().narrative.model_copy(
        update={"england_story": "England cruise — nothing to worry about.", "slot_rationales": {"73": "only one"}}
    )
)
VALID = build_submission(delta_vs_market=0.12, market_justification="Confirmed keeper news the books have not priced.")

SCRIPT = [
    tool_call_turn(("read_journal", {}), ("get_odds", {"market": "outrights"}), text="Memory and anchor first."),
    tool_call_turn(("web_search", {"query": "England squad news Croatia", "freshness": "pd"})),
    tool_call_turn(
        (
            "ledger_append",
            {
                "claim": "First-choice keeper confirmed fit by the FA",
                "source_url": "https://www.reuters.com/world/example-article-2026",
                "status": "confirmed",
                "mechanism": "keeper returns to the XI",
                "proposed_delta": 15.0,
                "team_id": "england",
            },
        ),
    ),
    tool_call_turn(("run_python", {"code": "print(0.62 * 0.97)"})),
    tool_call_turn(("run_simulation", {"rating_overrides": {"england": 15.0}, "n_sims": 300, "seed": 1})),
    tool_call_turn(
        ("write_journal", {"text": "Checked keeper news, ran sim.", "lessons": "Anchor on odds before news."}),
        ("submit_forecast", INVALID.model_dump()),
    ),
    tool_call_turn(("submit_forecast", VALID.model_dump()), text="Fixed the rationales and the dash."),
    tool_call_turn(("submit_forecast", VALID.model_dump()), text="Tripwire considered; the keeper news stands."),
]

K_SAMPLES = [
    {"rating_overrides": [{"team_id": "england", "delta_elo": 21.0, "cause": "keeper", "ledger_ids": ["led-0001"]}]},
    {"rating_overrides": [{"team_id": "england", "delta_elo": 9.0, "cause": "keeper", "ledger_ids": ["led-0001"]}]},
]


async def test_full_run(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        runs_root=tmp_path,
        lessons_path=tmp_path / "LESSONS.md",
        n_sims=300,
        agent_k_samples=3,
        agent_tool_budget=10,
    )
    runtime = build_runtime(
        run_id="e2e-run",
        tracer=InMemoryTracer(),
        caps=Caps(max_llm_calls=20, max_search_calls=5, max_fetch_calls=5, max_data_fetches=5),
        runs_root=tmp_path,
    )
    fake_llm = ScriptedLLM(turns=list(SCRIPT), structured=list(K_SAMPLES))
    deps = AgentDeps(
        runtime=runtime,
        llm=ObservedLLM(fake_llm, runtime),
        web=ObservedWeb(runtime=runtime, brave=FakeSearchClient(), fetch=FakeFetchClient()),
        odds=FakeOddsClient(),
        fixtures=FakeFixturesClient(),
        sim=EngineSimulation(),
        ledger=EvidenceLedger(tmp_path / "e2e-run" / "ledger.jsonl"),
        memory=RunMemory(runs_root=tmp_path, run_id="e2e-run", lessons_path=settings.lessons_path),
        quant=ObservedQuant(runtime),
        gate=BudgetGate(settings.agent_tool_budget),
        settings=settings,
        limits=ValidatorLimits(),
    )

    result = await run_master(deps, as_of="2026-06-09")
    runtime.shutdown()

    assert result.submission is not None
    assert not result.budget_exhausted
    assert result.validation_failures == 1

    by_team = {o.team_id: o.delta_elo for o in result.submission.rating_overrides}
    assert by_team == {"england": 15.0}
    assert result.disagreement is not None
    assert result.disagreement.k == 3
    assert result.disagreement.max_spread == pytest.approx(12.0)

    # Free tools (read_journal, run_python, ledger, journal, submit) never burn budget.
    assert deps.gate.used == 3
    # 8 scripted tool turns + 2 k-sample extractions, all charged and costed.
    assert runtime.budget.llm_calls == 10
    assert fake_llm.structured_count == 2
    assert runtime.budget.cost_micros > 0

    events = EventLog.read(runtime.paths.events)
    kinds = {e.kind for e in events}
    assert {"llm_call", "web_search", "data_fetch", "quant", "quant_exec", "ledger", "validation", "tripwire"} <= kinds
    summaries = [e.summary for e in events if e.kind == "validation"]
    assert any("rejected" in s for s in summaries)
    assert any("accepted" in s for s in summaries)

    assert deps.ledger.get("led-0001") is not None
    assert "Anchor on odds" in settings.lessons_path.read_text()
    assert (tmp_path / "e2e-run" / "journal.md").exists()
