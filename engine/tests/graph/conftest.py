from __future__ import annotations

from pathlib import Path

from wolves.agent.deps import AgentDeps
from wolves.agent.fakes import ScriptedLLM
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.sim_runner import EngineSimulation
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FakeFixturesClient
from wolves.clients.odds import FakeOddsClient, FakePolymarketClient
from wolves.config import Settings
from wolves.connectors import FakeFetchClient, FakeSearchClient, ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability import Caps, InMemoryTracer, build_runtime
from wolves.quant.observed import ObservedQuant
from wolves.tools._budget_gate import BudgetGate


def build_graph_deps(
    tmp_path: Path,
    *,
    settings: Settings | None = None,
    caps: Caps | None = None,
    structured: list[dict] | None = None,
    run_id: str = "graph-run",
) -> AgentDeps:
    settings = settings or Settings(
        _env_file=None,
        runs_root=tmp_path,
        n_sims=300,
    )
    runtime = build_runtime(run_id=run_id, tracer=InMemoryTracer(), caps=caps or Caps(), runs_root=tmp_path)
    return AgentDeps(
        runtime=runtime,
        llm=ObservedLLM(ScriptedLLM(turns=[], structured=structured or []), runtime),
        web=ObservedWeb(runtime=runtime, brave=FakeSearchClient(), fetch=FakeFetchClient()),
        odds=FakeOddsClient(),
        polymarket=FakePolymarketClient(),
        fixtures=FakeFixturesClient(),
        sim=EngineSimulation(),
        ledger=EvidenceLedger(tmp_path / run_id / "ledger.jsonl"),
        memory=RunMemory(runs_root=tmp_path, run_id=run_id, lessons_path=settings.lessons_path),
        quant=ObservedQuant(runtime),
        gate=BudgetGate(),
        settings=settings,
        limits=ValidatorLimits(),
    )
