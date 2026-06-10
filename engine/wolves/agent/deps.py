from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.scenarios import ScenarioRegistry
from wolves.agent.source_memory import SourceMemory
from wolves.agent.validator import ValidatorLimits
from wolves.agent_tools._budget_gate import BudgetGate
from wolves.clients.api_football import FixturesClient
from wolves.clients.odds import OddsClient, PolymarketClient
from wolves.config import Settings
from wolves.connectors.observed import ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability.runtime import ObservedRuntime
from wolves.quant.observed import ObservedQuant

if TYPE_CHECKING:
    from wolves.forecast import Forecaster
    from wolves.graph.artifacts import RunArtifactStore


TodoStatus = Literal["pending", "in_progress", "completed"]


class TodoItem(BaseModel):
    content: str
    status: TodoStatus = "pending"


@dataclass
class SubmissionState:
    """Run-level submission outcome. Shared by reference across per-node deps
    copies so the forecast node's submit tool writes where the runner reads."""

    accepted: ForecastSubmission | None = None
    validation_failures: int = 0
    escalation_fired: bool = False
    escalations: list[str] = field(default_factory=list)


@dataclass
class AgentDeps:
    """Everything a tool can reach. Nodes get a copy with their own actor and
    gate; the submission state stays shared by reference."""

    runtime: ObservedRuntime
    llm: ObservedLLM
    web: ObservedWeb
    odds: OddsClient
    polymarket: PolymarketClient
    fixtures: FixturesClient
    ledger: EvidenceLedger
    memory: RunMemory
    quant: ObservedQuant
    gate: BudgetGate
    settings: Settings
    limits: ValidatorLimits
    actor: str = "master"
    as_of: str = ""
    submission: SubmissionState = field(default_factory=SubmissionState)
    artifacts: RunArtifactStore | None = None
    forecaster: Forecaster | None = None
    source_memory: SourceMemory | None = None
    scenarios: ScenarioRegistry | None = None
    todos: list[TodoItem] = field(default_factory=list)
    python_calls: int = 0
