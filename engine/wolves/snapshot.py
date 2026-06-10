from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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


class RoundOpponents(BaseModel):
    """Opponent distribution for a later round, conditional on the group finish and the focus team reaching it."""

    round: str
    match: int
    city: str
    date: str
    reach_prob: float
    opponents: list[Candidate]


class FocusTeamPath(BaseModel):
    finish: str
    prob: float
    r32_match: int
    city: str
    date: str
    opponents: list[Candidate]
    onward: list[RoundOpponents] = Field(default_factory=list)


class ModalStep(BaseModel):
    round: str
    match: int
    city: str
    date: str
    opponent_id: str
    opponent_prob: float


class CityProb(BaseModel):
    city: str
    prob: float


class LockDate(BaseModel):
    """How certain the focus team's R32 city is once a group matchday completes; bookability signal."""

    date: str
    prob_locked: float
    locked_city_probs: dict[str, float]


class WhatIfOutcome(BaseModel):
    outcome: str
    prob: float
    finish_probs: dict[str, float]
    r32_city_probs: dict[str, float]


class WhatIfFixture(BaseModel):
    match: int
    date: str
    city: str
    opponent_id: str
    outcomes: list[WhatIfOutcome]


class FocusTeamBlock(BaseModel):
    team_id: str
    group: str
    finish_probs: dict[str, float]
    reach_probs: dict[str, float]
    paths: list[FocusTeamPath]
    modal_path: list[ModalStep] = Field(default_factory=list)
    city_probs: dict[str, list[CityProb]] = Field(default_factory=dict)
    lock_dates: list[LockDate] = Field(default_factory=list)
    what_if: list[WhatIfFixture] = Field(default_factory=list)


class GroupTeamStanding(BaseModel):
    team_id: str
    finish_probs: dict[str, float]
    expected_points: float


class GroupBlock(BaseModel):
    group: str
    teams: list[GroupTeamStanding]


class MatchProbs(BaseModel):
    """Forecast for one unplayed fixture. Group probabilities are within 90
    minutes; knockout figures are conditional on the modal pairing occurring."""

    match: int
    stage: str
    date: str
    city: str
    home_id: str
    away_id: str
    p_home: float
    p_away: float
    p_draw: float | None = None
    p_decided_90: float | None = None
    p_pairing: float | None = None
    modal_score: str | None = None


class RunMeta(BaseModel):
    run_id: str
    created_at: str
    as_of: str = ""
    n_sims: int
    engine_version: str
    kind: str


def run_day(meta: RunMeta) -> str:
    """The forecast day a run speaks for; runs are as_of-keyed, and the
    wall-clock created_at only stands in for replays of older snapshots."""
    return meta.as_of or meta.created_at[:10]


class NarrativeBlock(BaseModel):
    focus_story: str
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
    relevance: float | None = None
    source_tier: int | None = None
    retrieved_at: str | None = None
    retrieval_id: str | None = None
    created_at: str


class ScenarioWeightOut(BaseModel):
    name: str
    weight: float
    scenario_id: str | None = None
    ledger_ids: list[str] = Field(default_factory=list)


class WorldOut(BaseModel):
    """One published world's configuration, kept so live republishes can
    reapply the agent's adjustments without re-running the agent."""

    name: str
    weight: float
    perturbations: list[dict] = Field(default_factory=list)


class GovernorOut(BaseModel):
    scale: float = 1.0
    effective_d: float = 1.0


class AttributionOut(BaseModel):
    bracket_pp: dict[str, float] = Field(default_factory=dict)
    refit_pp: dict[str, float] = Field(default_factory=dict)
    residual_pp: dict[str, float] = Field(default_factory=dict)


class CalibrationSummary(BaseModel):
    matches_scored: int = 0
    brier: dict[str, float] = Field(default_factory=dict)
    log_loss: dict[str, float] = Field(default_factory=dict)
    adjustment_pnl: float | None = None
    governor_scale: float = 1.0


class AgentBlock(BaseModel):
    """Agent-run extras; absent on sim-only snapshots. Additive by design."""

    narrative: NarrativeBlock
    artifact_id: str = ""
    ledger_entries: list[LedgerEntryOut] = Field(default_factory=list)
    scenario_weights: list[ScenarioWeightOut] = Field(default_factory=list)
    worlds: list[WorldOut] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    market_justification: str = ""
    change_justification: str = ""
    inconsistency_note: str = ""
    attribution: AttributionOut | None = None
    governor: GovernorOut | None = None
    calibration: CalibrationSummary | None = None


class ChampionBlock(BaseModel):
    """Which trusted model produced the simulation numbers."""

    id: str
    version: str
    dataset_id: str
    half_life_days: float | None = None
    blend_weight: float = 0.0


class TeamInterval(BaseModel):
    team_id: str
    lo: float
    hi: float


class MarketsBlock(BaseModel):
    """Published title probabilities: model, de-vigged market and the blend."""

    model_config = ConfigDict(protected_namespaces=())

    model_probs: dict[str, float] = Field(default_factory=dict)
    market_probs: dict[str, float] = Field(default_factory=dict)
    blend_probs: dict[str, float] = Field(default_factory=dict)
    model_weight: float = 0.0


class TeamInfo(BaseModel):
    team_id: str
    name: str
    group: str
    elo: float
    rating: float = 0.0
    value_eur_m: float | None = None
    champion_prob: float = 0.0
    reach_probs: dict[str, float] = Field(default_factory=dict)


class Snapshot(BaseModel):
    """The engine-to-web contract; additive changes only, breaking changes bump SCHEMA_VERSION."""

    schema_version: int = SCHEMA_VERSION
    run: RunMeta
    focus: FocusTeamBlock
    slots: list[Slot]
    teams: list[TeamInfo]
    groups: list[GroupBlock] = Field(default_factory=list)
    matches: list[MatchProbs] = Field(default_factory=list)
    agent: AgentBlock | None = None
    champion: ChampionBlock | None = None
    intervals: list[TeamInterval] = Field(default_factory=list)
    markets: MarketsBlock | None = None
