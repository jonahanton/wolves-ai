from __future__ import annotations

from dataclasses import dataclass, field

from wolves.agent.contracts import ForecastSubmission, WorkerResult
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.sim_runner import SimulationApi
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FixturesClient
from wolves.clients.odds import OddsClient
from wolves.config import Settings
from wolves.connectors.observed import ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability.runtime import ObservedRuntime
from wolves.quant.observed import ObservedQuant
from wolves.tools._budget_gate import BudgetGate


@dataclass
class AgentDeps:
    """Everything a tool can reach. One instance per loop (master or worker);
    workers get a copy with their own actor, gate and toolset."""

    runtime: ObservedRuntime
    llm: ObservedLLM
    web: ObservedWeb
    odds: OddsClient
    fixtures: FixturesClient
    sim: SimulationApi
    ledger: EvidenceLedger
    memory: RunMemory
    quant: ObservedQuant
    gate: BudgetGate
    settings: Settings
    limits: ValidatorLimits
    actor: str = "master"
    accepted: ForecastSubmission | None = None
    validation_failures: int = 0
    tripwire_fired: bool = False
    python_calls: int = 0
    worker_reports: list[WorkerResult] = field(default_factory=list)
