from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.sim_runner import SimulationApi
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FixturesClient
from wolves.clients.odds import OddsClient, PolymarketClient
from wolves.config import Settings
from wolves.connectors.observed import ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability.runtime import ObservedRuntime
from wolves.quant.observed import ObservedQuant
from wolves.tools._budget_gate import BudgetGate

if TYPE_CHECKING:
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
    tripwire_fired: bool = False


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
    sim: SimulationApi
    ledger: EvidenceLedger
    memory: RunMemory
    quant: ObservedQuant
    gate: BudgetGate
    settings: Settings
    limits: ValidatorLimits
    actor: str = "master"
    submission: SubmissionState = field(default_factory=SubmissionState)
    artifacts: RunArtifactStore | None = None
    todos: list[TodoItem] = field(default_factory=list)
    python_calls: int = 0
