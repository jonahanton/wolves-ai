from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator, model_validator
from pydantic.alias_generators import to_camel

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
    mode: Literal["daily", "agent", "live"] = "daily"
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


class Health(BaseModel):
    status: Literal["ok"]
    uptime_s: float


class LiveForecast(BaseModel):
    source: Literal["pre_match", "in_match", "settled"]
    p_home: float
    p_away: float
    p_draw: float | None = None
    modal_score: str | None = None


class LiveFixture(BaseModel):
    external_id: int
    match: int | None
    status: Literal["scheduled", "live", "finished", "abandoned"]
    kickoff: str
    city: str | None = None
    minute: int | None = None
    home_id: str | None = None
    away_id: str | None = None
    home_name: str
    away_name: str
    home_goals: int | None = None
    away_goals: int | None = None
    home_reds: int = 0
    away_reds: int = 0
    forecast: LiveForecast | None = None
    message: str | None = None


class ScheduleDrift(BaseModel):
    match: int
    scheduled_kickoff: str
    provider_kickoff: str


class LiveState(BaseModel):
    schema_version: int
    generated_at: str
    fetched_at: str
    stale_after: str
    source: str
    poll_status: Literal["ok", "failed"]
    message: str | None = None
    live_match_count: int
    fixtures: list[LiveFixture]
    title_probs: dict[str, float]
    title_deltas_pp: dict[str, float]
    schedule_drift: list[ScheduleDrift] = Field(default_factory=list)
