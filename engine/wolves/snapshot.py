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


class ResultSetEntry(BaseModel):
    match: int
    home_id: str | None = None
    away_id: str | None = None
    home_goals: int
    away_goals: int
    winner: str | None = None
    source_fixture_id: int | None = None
    fetched_at: str | None = None


class ResultSetBlock(BaseModel):
    digest: str = ""
    results: list[ResultSetEntry] = Field(default_factory=list)


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


class TeamStoryOut(BaseModel):
    summary: str
    why: str


class NarrativeBlock(BaseModel):
    headline: str = ""
    team_stories: dict[str, TeamStoryOut] = Field(default_factory=dict)
    focus_story: str | None = None
    slot_rationales: dict[str, str] = Field(default_factory=dict)
    travel_memo: str | None = None


class LedgerEntryOut(BaseModel):
    id: str
    claim: str
    source_url: str
    # Joined from the article cache at snapshot build so the frontend can
    # name sources without exposing internal ledger machinery.
    title: str | None = None
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


class SourceRelevanceOut(BaseModel):
    """One source the agent ranked, fetched or cited during the run."""

    url: str
    title: str = ""
    hostname: str = ""
    tier: int | None = None
    score: float | None = None
    reason: str = ""
    sub_question: str = ""
    ranked: bool = False
    cited: bool = False
    fetched: bool = False
    seen_in_run: str | None = None
    retrieval_id: str | None = None
    created_by: str = ""


class ScenarioWeightOut(BaseModel):
    name: str
    weight: float
    scenario_id: str | None = None
    ledger_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    camp: str = ""
    label: str = ""
    summary: str = ""


class CampOut(BaseModel):
    key: str
    label: str = ""
    summary: str = ""
    weight: float = 0.0
    order: int = 0


class MarketGapOut(BaseModel):
    """A published market stance with separate model and forecast comparisons."""

    team_id: str
    model_prob: float
    market_prob: float
    forecast_prob: float | None = None
    model_market_gap_pp: float | None = None
    forecast_market_gap_pp: float | None = None
    gap_pp: float
    floor_multiple: float | None = None
    direction: str
    model_direction: str = ""


class WorldOut(BaseModel):
    """One published world's configuration, kept so live republishes can
    reapply the agent's adjustments without re-running the agent."""

    name: str
    weight: float
    perturbations: list[dict] = Field(default_factory=list)
    latent_effects: list[dict] = Field(default_factory=list)
    title_probs: dict[str, float] = Field(default_factory=dict)
    # Match id -> {home, draw, away}; the surface the spread P&L is scored on.
    match_probs: dict[str, dict[str, float]] = Field(default_factory=dict)


class QuantFindingOut(BaseModel):
    """One quant node's headline, surfaced so the run page can show the analysis."""

    node_id: str
    summary: str
    headline_value: float | None = None
    findings: list[str] = Field(default_factory=list)


class GovernorOut(BaseModel):
    scale: float = 1.0
    effective_d: float = 1.0


class MovementOut(BaseModel):
    previous_prob: float
    current_prob: float
    delta_pp: float


class AttributionOut(BaseModel):
    bracket_pp: dict[str, float] = Field(default_factory=dict)
    refit_pp: dict[str, float] = Field(default_factory=dict)
    residual_pp: dict[str, float] = Field(default_factory=dict)
    movement: dict[str, MovementOut] = Field(default_factory=dict)


class CalibrationSummary(BaseModel):
    matches_scored: int = 0
    brier: dict[str, float] = Field(default_factory=dict)
    log_loss: dict[str, float] = Field(default_factory=dict)
    adjustment_pnl: float | None = None
    governor_scale: float = 1.0
    spread_pnl: float | None = None
    band_coverage: float | None = None
    movement_ratio: float | None = None


class ProvenanceOut(BaseModel):
    news_considered: int = 0
    news_material: int = 0
    news_excluded: int = 0
    market_disagreements: int = 0
    noise_floor_pp: float = 0.0
    n_worlds: int = 1
    n_camps: int = 1


class RevisionOut(BaseModel):
    """Post-acceptance revision trace for later counterfactual scoring."""

    revisions_used: int = 0
    counterfactual_artifact_id: str = ""
    revision_rationale: str = ""


class FinalisationOut(BaseModel):
    artifact_id: str
    submission_fingerprint: str
    validation_issue_counts: dict[str, int] = Field(default_factory=dict)
    referee_status: str
    referee_reason: str = ""
    advertised_ceiling_usd: float
    forecast_reserved_usd: float
    referee_reserved_usd: float
    settled_cost_usd: float


class AgentBlock(BaseModel):
    """Agent-run extras; absent on sim-only snapshots. Additive by design."""

    narrative: NarrativeBlock
    artifact_id: str = ""
    ledger_entries: list[LedgerEntryOut] = Field(default_factory=list)
    sources: list[SourceRelevanceOut] = Field(default_factory=list)
    scenario_weights: list[ScenarioWeightOut] = Field(default_factory=list)
    camps: list[CampOut] = Field(default_factory=list)
    worlds: list[WorldOut] = Field(default_factory=list)
    quant_findings: list[QuantFindingOut] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    market_gaps: list[MarketGapOut] = Field(default_factory=list)
    market_justification: str = ""
    change_justification: str = ""
    inconsistency_note: str = ""
    news_impacts: dict[str, str] = Field(default_factory=dict)
    copy_guard_version: int | None = None
    attribution: AttributionOut | None = None
    governor: GovernorOut | None = None
    calibration: CalibrationSummary | None = None
    provenance: ProvenanceOut | None = None
    branch_audit: dict[str, object] | None = None
    world_metadata: dict[str, dict[str, object]] = Field(default_factory=dict)
    revision: RevisionOut | None = None
    finalisation: FinalisationOut | None = None


class ChampionBlock(BaseModel):
    """Which trusted model produced the simulation numbers."""

    id: str
    version: str
    dataset_id: str
    half_life_days: float | None = None
    blend_weight: float = 0.0
    # Played results overlaid into the strength refit.
    results_overlaid: int = 0


class TeamInterval(BaseModel):
    team_id: str
    lo: float
    hi: float


class TeamDistributions(BaseModel):
    """Per-stage epistemic spread for one team: open cells carry the quantile
    vector, settled cells carry the outcome as a flag, never both."""

    quantiles: dict[str, list[float]] = Field(default_factory=dict)
    settled: dict[str, int] = Field(default_factory=dict)


class NewsItemOut(BaseModel):
    """One sourced news item joined to its price; impact is the agent's why."""

    ledger_id: str
    claim: str
    mechanism: str
    source_url: str
    title: str | None = None
    hostname: str = ""
    status: str = ""
    signed_delta_pp: float | None = None
    material: bool = False
    excluded_reason: str | None = None
    impact: str | None = None


class TeamDriver(BaseModel):
    """Per-camp chances, any market stance, sourced news and disagreement shape for one team."""

    camp_probs: dict[str, float] = Field(default_factory=dict)
    market_gap: MarketGapOut | None = None
    news: list[NewsItemOut] = Field(default_factory=list)
    has_story: bool = False
    higher_camp: str | None = None
    spread_pp: float = 0.0
    noise_floor_pp: float = 0.0


class DistributionsBlock(BaseModel):
    """Confidence in each published number: weighted (world x parameter-draw)
    quantiles per team per stage. The headline stays the mean; this block is
    epistemic dispersion ("how settled the number is"), never the aleatory
    outcome range ("the tournament could still go any way"), which is a
    separate named quantity."""

    quantile_levels: list[float] = Field(default_factory=list)
    provenance: str = "parameters_only"
    n_worlds: int = 1
    width_floored: bool = False
    sidecar: str = ""
    teams: dict[str, TeamDistributions] = Field(default_factory=dict)
    drivers: dict[str, TeamDriver] = Field(default_factory=dict)


class MarketsBlock(BaseModel):
    """Transparency block: model view, de-vigged market and a reference blend.

    On agent runs teams[] is the published headline and blend_probs is
    comparison only; deterministic runs publish blend_probs as teams[]."""

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
    distributions: DistributionsBlock | None = None
    result_set: ResultSetBlock = Field(default_factory=ResultSetBlock)
