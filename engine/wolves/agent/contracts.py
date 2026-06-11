from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LedgerStatus = Literal["confirmed", "probable", "rumour"]


class Narrative(BaseModel):
    focus_story: str
    slot_rationales: dict[str, str] = Field(default_factory=dict)
    travel_memo: str


class ScenarioWeight(BaseModel):
    """One named judgement point: a world's weight and the evidence behind it."""

    name: str
    weight: float = Field(ge=0.0, le=1.0)
    scenario_id: str | None = None
    ledger_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class ForecastSubmission(BaseModel):
    """Submission by artifact reference: the published distribution must exist
    as a computed run artifact (a mixture or simulation output); typed tokens
    never become published numbers."""

    artifact_id: str
    narrative: Narrative
    scenario_weights: list[ScenarioWeight] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    market_justification: str = ""
    change_justification: str = ""
    inconsistency_note: str = ""


class EvidenceItem(BaseModel):
    claim: str
    source_url: str
    quote: str = ""
    stance: str = ""
