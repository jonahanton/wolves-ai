from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints
from pydantic.alias_generators import to_camel

TASK_ARN_PATTERN = r"^arn:aws:ecs:[a-z0-9-]+:\d{12}:task/[A-Za-z0-9_-]+/[a-f0-9]+$"


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


class ScheduleState(WireModel):
    enabled: bool
    cron: str


class ScheduleUpdate(WireModel):
    enabled: StrictBool


class RunStarted(WireModel):
    task_arn: str


class StopRequest(WireModel):
    task_arn: Annotated[str, StringConstraints(pattern=TASK_ARN_PATTERN)]


class StopResult(WireModel):
    stopped: str


class Health(BaseModel):
    status: Literal["ok"]
    uptime_s: float
