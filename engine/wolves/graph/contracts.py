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

    ops: list[NodePatch] = Field(default_factory=list)
    stop: bool = False
    reason: str = ""


class LedgerEvidence(EvidenceItem):
    """Evidence rich enough for the runner to convert into a ledger entry."""

    status: LedgerStatus = "probable"
    mechanism: str = ""
    proposed_delta: float = 0.0
    expiry: str | None = None
    team_id: str | None = None


class ResearchOutput(BaseModel):
    summary: str
    evidence: list[LedgerEvidence] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class QuantOutput(BaseModel):
    summary: str
    findings: list[str] = Field(default_factory=list)
    headline_value: float | None = None


class ForecastOutput(BaseModel):
    """Acceptance happens via the submit tool, never via this output."""

    summary: str


class CritiqueOutput(BaseModel):
    summary: str
    challenges: list[str] = Field(default_factory=list)


class NodeOutcome(BaseModel):
    node_id: str
    kind: NodeKind
    ok: bool
    artifact_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    requests: int = 0
