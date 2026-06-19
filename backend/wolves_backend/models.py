from __future__ import annotations

import re
from datetime import date  # noqa: TC003  pydantic resolves field annotations at runtime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator, model_validator
from pydantic.alias_generators import to_camel

# TC001: pydantic resolves field annotations at runtime.
from wolves.live_state import LiveForecast  # noqa: TC001

TASK_ARN_PATTERN = r"^arn:aws:ecs:[a-z0-9-]+:\d{12}:task/[A-Za-z0-9_-]+/[a-f0-9]+$"

CRON_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9*?,/#LW-]+$")


class WireModel(BaseModel):
    """Camel-cased wire contract shared with the web app."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class RunRecord(WireModel):
    run_id: str
    created_at: str
    s3_key: str
    status: Literal["completed", "failed"]
    cost: float
    duration_s: float
    kind: str


class RunHistory(WireModel):
    runs: list[RunRecord]


class SnapshotRef(WireModel):
    run_id: str
    as_of: str
    kind: str
    key: str


class SnapshotIndex(WireModel):
    snapshots: list[SnapshotRef]


class EventsSummary(WireModel):
    count: int
    kinds: dict[str, int]
    first_ts: str | None
    last_ts: str | None


class ArtifactRecord(WireModel):
    id: str
    kind: str
    summary: str
    created_at: str
    created_by: str


class RunDetail(WireModel):
    record: RunRecord | None
    has_journal: bool
    events: EventsSummary | None
    artifacts: list[ArtifactRecord]


class TeamHistoryPoint(WireModel):
    run_id: str
    as_of: str
    champion_prob: float
    reach_probs: dict[str, float]
    market_prob: float | None = None
    blend_prob: float | None = None


class TeamHistory(WireModel):
    team_id: str
    points: list[TeamHistoryPoint]


class TeamHistories(WireModel):
    histories: list[TeamHistory]


class OddsDates(WireModel):
    dates: list[str]


class ScheduleState(WireModel):
    enabled: bool
    cron: str


class ScheduleUpdate(WireModel):
    enabled: StrictBool
    cron: str | None = None

    @field_validator("cron")
    @classmethod
    def _validate_cron(cls, value: str | None) -> str | None:
        if value is None:
            return None
        fields = value.split()
        if len(fields) != 6 or not all(CRON_FIELD_PATTERN.fullmatch(field) for field in fields):
            raise ValueError("must be six space-separated EventBridge cron fields")
        return " ".join(fields)


class RunNowRequest(WireModel):
    force: StrictBool = False
    mode: Literal["daily", "agent"] = "daily"
    ceiling_usd: float | None = Field(default=None, ge=0.01, le=8.0)

    @model_validator(mode="after")
    def _ceiling_only_for_agent(self) -> RunNowRequest:
        if self.mode != "agent" and self.ceiling_usd is not None:
            raise ValueError("ceilingUsd only applies to agent runs")
        return self


class RunStarted(WireModel):
    task_arn: str


class ActiveRun(WireModel):
    task_arn: str
    last_status: str
    started_at: str | None


class ActiveRuns(WireModel):
    tasks: list[ActiveRun]


class StopRequest(WireModel):
    task_arn: Annotated[str, StringConstraints(pattern=TASK_ARN_PATTERN)]


class StopResult(WireModel):
    stopped: str


class PinIn(WireModel):
    match: int = Field(ge=1, le=104)
    home_goals: int = Field(ge=0, le=9)
    away_goals: int = Field(ge=0, le=9)


class SimulateRequest(WireModel):
    pins: list[PinIn] = Field(default_factory=list, max_length=8)
    n_sims: int = Field(default=10_000, ge=1_000, le=20_000)
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    results_until: date | None = None


class EngineBlock(WireModel):
    fitted_run_id: str
    model_id: str
    as_of: str
    n_sims: int
    seed: int


class SimulateResponse(WireModel):
    engine: EngineBlock
    baseline: dict[str, dict[str, float]]
    pinned: dict[str, dict[str, float]]


class MatchGrid(WireModel):
    match: int
    stage: str
    home_id: str
    away_id: str
    grid: list[list[float]]
    p_home: float
    p_draw: float
    p_away: float
    fitted_run_id: str


class PlayedResultOut(WireModel):
    match: int
    date: str
    stage: str
    home_id: str | None
    away_id: str | None
    home_goals: int
    away_goals: int
    winner: str | None


class ResultsOut(WireModel):
    results: list[PlayedResultOut]


class DayPolicyOut(WireModel):
    date: str
    phase: str
    ceiling_usd: float
    big_teams: list[str]


class RunPolicy(WireModel):
    today: DayPolicyOut
    calendar: list[DayPolicyOut]


class StageImpact(WireModel):
    agent: float
    after_results: float
    estimated: float
    from_results_pp: float
    from_ingame_pp: float
    display_floor_pp: float


class TeamImpact(WireModel):
    title: StageImpact
    reach: dict[Literal["r32", "r16", "qf", "sf", "final"], StageImpact]
    exit: dict[Literal["groups", "r32", "r16", "qf", "sf", "final", "champion"], StageImpact]


class LiveWdl(WireModel):
    p_home: list[float]
    p_draw: list[float]
    p_away: list[float]


class WdlKeyframe(WireModel):
    minute: int
    home_goals: int
    away_goals: int
    wdl: LiveWdl


class StatPoint(WireModel):
    minute: int
    home_shots_on: int | None = None
    away_shots_on: int | None = None
    home_total_shots: int | None = None
    away_total_shots: int | None = None
    home_possession: float | None = None
    away_possession: float | None = None


class ImpactFixture(WireModel):
    match: int | None
    home_id: str | None
    away_id: str | None
    home_name: str
    away_name: str
    home_goals: int | None
    away_goals: int | None
    minute: int | None
    status: str
    p_home: float | None
    p_draw: float | None
    p_away: float | None
    home_shots_on: int | None = None
    away_shots_on: int | None = None
    home_total_shots: int | None = None
    away_total_shots: int | None = None
    home_possession: float | None = None
    away_possession: float | None = None
    wdl_draws: LiveWdl | None = None
    wdl_keyframes: list[WdlKeyframe] = []
    stat_track: list[StatPoint] = []


class ImpactResult(WireModel):
    match: int
    home_id: str | None
    away_id: str | None
    home_goals: int
    away_goals: int
    winner: str | None = None
    source_fixture_id: int | None = None
    fetched_at: str | None = None
    kind: Literal["new", "corrected"]


class Impact(WireModel):
    agent_run_id: str
    agent_as_of: str
    agent_created_at: str
    then_basis: str
    now_basis: str
    current_fit_run_id: str
    current_fit_as_of: str
    dataset_id: str
    agent_result_set_digest: str
    current_result_set_digest: str
    live_mode: Literal["score_hold", "in_match_distribution", "none"]
    n_sims: int
    seed: int
    parameter_uncertainty: bool
    generated_at: str
    results_since_agent: list[ImpactResult]
    fixtures: list[ImpactFixture]
    teams: dict[str, TeamImpact]


class Health(BaseModel):
    status: Literal["ok"]
    uptime_s: float


class LiveHistoryFixture(BaseModel):
    external_id: int
    match: int | None
    status: Literal["scheduled", "live", "finished", "abandoned"]
    minute: int | None = None
    home_goals: int | None = None
    away_goals: int | None = None
    forecast: LiveForecast | None = None


class LiveHistoryPoint(BaseModel):
    fetched_at: str
    fixtures: list[LiveHistoryFixture]


class LiveHistory(BaseModel):
    date: str
    points: list[LiveHistoryPoint]
