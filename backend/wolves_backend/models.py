from __future__ import annotations

import re
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


class DayPolicyOut(WireModel):
    date: str
    phase: str
    ceiling_usd: float
    big_teams: list[str]


class RunPolicy(WireModel):
    today: DayPolicyOut
    calendar: list[DayPolicyOut]


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
