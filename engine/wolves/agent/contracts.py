from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LedgerStatus = Literal["confirmed", "probable", "rumour"]


class TeamStory(BaseModel):
    summary: str
    why: str


class Narrative(BaseModel):
    headline: str = ""
    team_stories: dict[str, TeamStory] = Field(default_factory=dict)


class Camp(BaseModel):
    key: str
    label: str = ""
    summary: str = ""
    order: int = 0


class ScenarioWeight(BaseModel):
    """One named judgement point: a world's weight and the evidence behind it."""

    name: str
    weight: float = Field(ge=0.0, le=1.0)
    scenario_id: str | None = None
    ledger_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    camp: str = ""
    label: str = ""
    summary: str = ""


class MarketGap(BaseModel):
    """One team's market stance; emitted only where a stance was taken."""

    team_id: str
    model_prob: float = Field(ge=0.0, le=1.0)
    market_prob: float = Field(ge=0.0, le=1.0)
    gap_pp: float
    floor_multiple: float | None = None


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
    market_gaps: list[MarketGap] = Field(default_factory=list)
    camps: list[Camp] = Field(default_factory=list)
    news_impacts: dict[str, str] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    claim: str
    source_url: str
    quote: str = ""
    stance: str = ""
