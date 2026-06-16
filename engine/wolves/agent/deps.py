from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

from wolves.agent.article_cache import ArticleCache
from wolves.agent.contracts import ForecastSubmission
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.relevance_memory import RelevanceMemory
from wolves.agent.scenarios import ScenarioRegistry
from wolves.agent.source_memory import SourceMemory
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FixturesClient
from wolves.clients.odds import OddsClient, PolymarketClient
from wolves.config import Settings
from wolves.connectors.observed import ObservedWeb
from wolves.llm.observed import ObservedLLM
from wolves.observability.runtime import ObservedRuntime
from wolves.quant.observed import ObservedQuant
from wolves.toolkit._budget_gate import BudgetGate

if TYPE_CHECKING:
    from wolves.agent.publish_surface import PublishSurface
    from wolves.forecast import Forecaster
    from wolves.graph.artifacts import RunArtifactStore


TodoStatus = Literal["pending", "in_progress", "completed"]


class TodoItem(BaseModel):
    content: str
    status: TodoStatus = "pending"


@dataclass
class ValidatorAnchors:
    """Validator reference distributions resolved once per run: the frozen
    baseline is a 50k-sim recompute, far too slow to repeat per attempt."""

    baseline_titles: dict[str, float] | None
    market_titles: dict[str, float] | None


@dataclass
class SubmissionState:
    """Run-level submission outcome. Shared by reference across per-node deps
    copies so the forecast node's submit tool writes where the runner reads."""

    accepted: ForecastSubmission | None = None
    validation_failures: int = 0
    referee_interventions: int = 0
    referee_approved: set[str] = field(default_factory=set)
    referee_replan_required: bool = False
    publication_blocked: bool = False
    escalation_fired: bool = False
    escalations: list[str] = field(default_factory=list)
    # The submission that validated clean but was withheld by the escalation
    # pause; the last resort when the steelman round never completes.
    last_clean: ForecastSubmission | None = None
    last_clean_escalations: list[str] = field(default_factory=list)
    checked_clean: ForecastSubmission | None = None
    copy_repair_required: bool = False
    copy_issue_signature: tuple[str, ...] | None = None
    copy_issue_repeats: int = 0
    copy_repair_blocked: bool = False
    anchors: ValidatorAnchors | None = None
    # Spread rows are a multi-world resimulation; cached per cited artifact.
    spread_by_artifact: dict[str, dict | None] = field(default_factory=dict)
    publish_surface_by_artifact: dict[tuple[str, int, int], PublishSurface] = field(default_factory=dict)
    # last_accepted is the fallback if a revision fails; counterfactual keeps
    # the first-accepted submission for later scoring.
    revisions_used: int = 0
    last_accepted: ForecastSubmission | None = None
    counterfactual: ForecastSubmission | None = None
    premortem_seen: set[str] = field(default_factory=set)


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
    referee_llm: ObservedLLM | None = None
    as_of: str = ""
    disable_continuity: bool = False
    publish_requested_n_sims: int | None = None
    publish_seed: int = 0
    submission: SubmissionState = field(default_factory=SubmissionState)
    artifacts: RunArtifactStore | None = None
    forecaster: Forecaster | None = None
    source_memory: SourceMemory | None = None
    articles: ArticleCache | None = None
    relevance_memory: RelevanceMemory | None = None
    scenarios: ScenarioRegistry | None = None
    market_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    market_cache_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    todos: list[TodoItem] = field(default_factory=list)
    python_calls: int = 0
