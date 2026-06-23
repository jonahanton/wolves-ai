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
    """Canonical model, market and published probabilities for one market stance."""

    team_id: str
    model_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    market_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    forecast_prob: float | None = Field(default=None, ge=0.0, le=1.0)
    model_market_gap_pp: float | None = None
    forecast_market_gap_pp: float | None = None
    gap_pp: float = 0.0
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
    # On a post-acceptance revision, why the forecast was revised or ratified,
    # in at most two sentences; empty on a first-pass submission.
    revision_rationale: str = ""
    market_gaps: list[MarketGap] = Field(default_factory=list)
    camps: list[Camp] = Field(default_factory=list)
    news_impacts: dict[str, str] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    claim: str
    source_url: str
    quote: str = ""
    stance: str = ""
