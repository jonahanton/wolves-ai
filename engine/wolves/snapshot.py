from __future__ import annotations

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class Candidate(BaseModel):
    team_id: str
    prob: float


class SlotSide(BaseModel):
    label: str
    candidates: list[Candidate]


class Slot(BaseModel):
    match: int
    stage: str
    date: str
    city: str
    home: SlotSide
    away: SlotSide


class EnglandPath(BaseModel):
    finish: str
    prob: float
    r32_match: int
    city: str
    date: str
    opponents: list[Candidate]


class EnglandBlock(BaseModel):
    team_id: str
    group: str
    finish_probs: dict[str, float]
    reach_probs: dict[str, float]
    paths: list[EnglandPath]


class RunMeta(BaseModel):
    run_id: str
    created_at: str
    n_sims: int
    engine_version: str
    kind: str


class NarrativeBlock(BaseModel):
    england_story: str
    slot_rationales: dict[str, str] = Field(default_factory=dict)
    travel_memo: str


class LedgerEntryOut(BaseModel):
    id: str
    claim: str
    source_url: str
    status: str
    mechanism: str
    proposed_delta: float = 0.0
    expiry: str | None = None
    team_id: str | None = None
    created_at: str


class RatingOverrideOut(BaseModel):
    team_id: str
    delta_elo: float
    cause: str
    ledger_ids: list[str] = Field(default_factory=list)


class DisagreementOut(BaseModel):
    k: int
    per_team_spread: dict[str, float] = Field(default_factory=dict)
    max_spread: float = 0.0
    mean_spread: float = 0.0


class CalibrationSummary(BaseModel):
    matches_scored: int = 0
    brier: dict[str, float] = Field(default_factory=dict)
    log_loss: dict[str, float] = Field(default_factory=dict)
    adjustment_pnl: float | None = None
    governor_scale: float = 1.0


class AgentBlock(BaseModel):
    """Agent-run extras; absent on sim-only snapshots. Additive by design."""

    narrative: NarrativeBlock
    ledger_entries: list[LedgerEntryOut] = Field(default_factory=list)
    rating_overrides: list[RatingOverrideOut] = Field(default_factory=list)
    disagreement: DisagreementOut | None = None
    calibration: CalibrationSummary | None = None


class TeamInfo(BaseModel):
    team_id: str
    name: str
    group: str
    elo: float


class Snapshot(BaseModel):
    """The engine-to-web contract; additive changes only, breaking changes bump SCHEMA_VERSION."""

    schema_version: int = SCHEMA_VERSION
    run: RunMeta
    england: EnglandBlock
    slots: list[Slot]
    teams: list[TeamInfo]
    agent: AgentBlock | None = None
