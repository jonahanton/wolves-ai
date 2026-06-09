from __future__ import annotations

from pathlib import Path

from wolves.agent.contracts import ResearchBrief
from wolves.agent.deps import AgentDeps
from wolves.agent.fakes import ScriptedLLM, tool_call_turn
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.researcher import run_researcher
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FakeFixturesClient
from wolves.clients.odds import FakeOddsClient
from wolves.config import Settings
from wolves.connectors import FakeFetchClient, FakeSearchClient, ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability import Caps, InMemoryTracer, build_runtime
from wolves.quant.observed import ObservedQuant
from wolves.sim.api import SimOutputs
from wolves.tools._budget_gate import BudgetGate

REPORT = {
    "objective": "England keeper fitness",
    "summary": "Keeper trained in full; club and FA statements agree.",
    "evidence": [
        {
            "claim": "Keeper trained in full on Monday",
            "source_url": "https://www.reuters.com/world/example-article-2026",
            "quote": "trained in full",
        }
    ],
    "signals": ["follow up after the pre-match press conference"],
}


def _deps(tmp_path: Path, llm: ScriptedLLM, *, researcher_budget: int) -> AgentDeps:
    settings = Settings(
        _env_file=None,
        runs_root=tmp_path,
        lessons_path=tmp_path / "LESSONS.md",
        researcher_tool_budget=researcher_budget,
        researcher_max_turns=4,
    )
    runtime = build_runtime(run_id="worker-run", tracer=InMemoryTracer(), caps=Caps(), runs_root=tmp_path)
    return AgentDeps(
        runtime=runtime,
        llm=ObservedLLM(llm, runtime),
        web=ObservedWeb(runtime=runtime, brave=FakeSearchClient(), fetch=FakeFetchClient()),
        odds=FakeOddsClient(),
        fixtures=FakeFixturesClient(),
        sim=_StubSim(),
        ledger=EvidenceLedger(tmp_path / "ledger.jsonl"),
        memory=RunMemory(runs_root=tmp_path, run_id="worker-run", lessons_path=tmp_path / "LESSONS.md"),
        quant=ObservedQuant(runtime),
        gate=BudgetGate(1),
        settings=settings,
        limits=ValidatorLimits(),
    )


class _StubSim:
    def run_simulation(
        self,
        rating_overrides: dict[str, float],
        fixture_goal_offsets: dict[int, tuple[float, float]],
        n_sims: int,
        seed: int | None,
    ) -> SimOutputs:
        raise AssertionError("researchers must not reach the sim")


async def test_worker_reports_findings_without_touching_master_budget(tmp_path: Path):
    llm = ScriptedLLM(
        turns=[
            tool_call_turn(("web_search", {"query": "England keeper fitness"})),
            tool_call_turn(("report_findings", REPORT)),
        ]
    )
    deps = _deps(tmp_path, llm, researcher_budget=4)
    brief = ResearchBrief(objective="England keeper fitness", brief="Confirm whether the keeper is fit.")

    with deps.runtime.run_trace():
        result = await run_researcher(deps, brief, worker_id="researcher-1")
    deps.runtime.shutdown()

    assert result.summary.startswith("Keeper trained in full")
    assert result.signals == ["follow up after the pre-match press conference"]
    assert deps.gate.used == 0


async def test_worker_exhausting_turns_returns_a_signal_not_nothing(tmp_path: Path):
    llm = ScriptedLLM(
        turns=[tool_call_turn(("web_search", {"query": f"query {i}"})) for i in range(4)],
    )
    deps = _deps(tmp_path, llm, researcher_budget=8)
    brief = ResearchBrief(objective="open-ended", brief="Search forever.")

    with deps.runtime.run_trace():
        result = await run_researcher(deps, brief, worker_id="researcher-1")
    deps.runtime.shutdown()

    assert "turns_exhausted" in result.signals[0]
