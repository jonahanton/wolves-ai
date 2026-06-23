from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from wolves.agent.contracts import EvidenceItem, LedgerStatus

NodeKind = Literal["research", "quant", "forecast", "critic"]


class Brief(BaseModel):
    """The master's contract with one worker node."""

    node_id: str
    kind: NodeKind
    objective: str
    brief: str
    input_artifact_ids: list[str] = Field(default_factory=list)


class NodePatch(Brief):
    """One graph-patch operation: open a line of inquiry, optionally
    superseding an earlier node it re-briefs or reconciles."""

    replaces: str | None = None


class GraphPatch(BaseModel):
    """The master's wave plan: patches the runtime admits against caps."""

    ops: list[NodePatch] = Field(
        default_factory=list,
        description="The node briefs to run next wave. The plan lives here, never in reason; required unless stop.",
    )
    stop: bool = False
    reason: str = Field(
        default="",
        description="One short paragraph of planning rationale. Never describe nodes here that ops does not carry.",
    )


class LedgerEvidence(EvidenceItem):
    """Evidence rich enough for the runner to convert into a ledger entry."""

    status: LedgerStatus = "probable"
    mechanism: str = ""
    proposed_delta: float = 0.0
    expiry: str | None = None
    team_id: str | None = None
    relevance: float | None = None
    retrieval_id: str | None = None


class CandidateBranch(BaseModel):
    """A research hypothesis for quant to price, collapse or reject."""

    branch_id: str = Field(min_length=1)
    teams: list[str] = Field(default_factory=list)
    hypothesis: str = Field(min_length=1)
    support: str = Field(min_length=1)
    collapse_condition: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    evidence_indices: list[int] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    suggested_quant_question: str = Field(min_length=1)
    parent_branch_ids: list[str] = Field(default_factory=list)


class ResearchOutput(BaseModel):
    summary: str
    evidence: list[LedgerEvidence] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    candidate_branches: list[CandidateBranch] = Field(default_factory=list)


class PricedItem(BaseModel):
    """One ledger item's signed title delta in pp, materiality and exclusion reason."""

    ledger_id: str
    signed_delta_pp: float | None = None
    material: bool = False
    excluded_reason: str | None = None
    noise_floor_pp: float | None = None


class QuantOutput(BaseModel):
    summary: str
    findings: list[str] = Field(default_factory=list)
    headline_value: float | None = None
    priced_items: list[PricedItem] = Field(default_factory=list)


class ForecastOutput(BaseModel):
    """Acceptance happens via the submit tool, never via this output."""

    summary: str


class CritiqueOutput(BaseModel):
    summary: str
    challenges: list[str] = Field(default_factory=list)
    # implied_shift_pp is advisory triage only; the gate reads the priced shift.
    tail_branches: list[CandidateBranch] = Field(default_factory=list)
    revision_recommendation: str = ""
    implied_shift_pp: float | None = None


class NodeOutcome(BaseModel):
    node_id: str
    kind: NodeKind
    ok: bool
    artifact_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    requests: int = 0
    flags: list[str] = Field(default_factory=list)
