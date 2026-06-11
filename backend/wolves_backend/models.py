from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints, field_validator
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
