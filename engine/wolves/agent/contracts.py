from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LedgerStatus = Literal["confirmed", "probable", "rumour"]


class RatingOverride(BaseModel):
    team_id: str
    delta_elo: float
    cause: str
    ledger_ids: list[str] = Field(default_factory=list)


class FixtureOffset(BaseModel):
    match: int
    home_goals: float
    away_goals: float
    expiry: str
    ledger_ids: list[str] = Field(default_factory=list)


class Narrative(BaseModel):
    england_story: str
    slot_rationales: dict[str, str] = Field(default_factory=dict)
    travel_memo: str


class ForecastSubmission(BaseModel):
    """The agent's final output, accepted only through the submit validator."""

    rating_overrides: list[RatingOverride] = Field(default_factory=list)
    fixture_offsets: list[FixtureOffset] = Field(default_factory=list)
    england_reach_probs: dict[str, float] = Field(default_factory=dict)
    narrative: Narrative
    delta_vs_market: float = 0.0
    market_justification: str = ""
    delta_vs_yesterday: float = 0.0
    change_justification: str = ""


class EvidenceItem(BaseModel):
    claim: str
    source_url: str
    quote: str = ""
    stance: str = ""


class ResearchBrief(BaseModel):
    objective: str
    brief: str
    input_artifact_ids: list[str] = Field(default_factory=list)


class WorkerResult(BaseModel):
    objective: str
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class OverrideSample(BaseModel):
    """One re-extraction of the final rating overrides from the same dossier."""

    rating_overrides: list[RatingOverride] = Field(default_factory=list)


class Disagreement(BaseModel):
    """K-sample spread of the final rating overrides, per team and summarised."""

    k: int
    per_team_spread: dict[str, float] = Field(default_factory=dict)
    max_spread: float = 0.0
    mean_spread: float = 0.0
