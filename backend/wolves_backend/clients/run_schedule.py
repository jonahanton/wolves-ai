from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from wolves_backend.errors import UpstreamError
from wolves_backend.models import ScheduleState


class RunSchedule:
    """EventBridge Scheduler control for the daily engine run."""

    def __init__(self, *, schedule_name: str, region: str, client: Any | None = None) -> None:
        self._schedule_name = schedule_name
        self._client = client or boto3.client("scheduler", region_name=region)

    def state(self) -> ScheduleState:
        schedule = self._get()
        return ScheduleState(enabled=schedule.get("State") == "ENABLED", cron=schedule.get("ScheduleExpression", ""))

    def set_enabled(self, *, enabled: bool) -> ScheduleState:
        # UpdateSchedule replaces the whole schedule, so echo back every field
        # from GetSchedule with only State changed. Absent optional fields are
        # dropped rather than passed as None, which boto3 rejects.
        current = self._get()
        echoed = {
            field: current[field]
            for field in (
                "Name",
                "GroupName",
                "ScheduleExpression",
                "ScheduleExpressionTimezone",
                "FlexibleTimeWindow",
                "Target",
            )
            if current.get(field) is not None
        }
        try:
            self._client.update_schedule(**echoed, State="ENABLED" if enabled else "DISABLED")
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("scheduler", str(exc)) from exc
        return ScheduleState(enabled=enabled, cron=current.get("ScheduleExpression", ""))

    def _get(self) -> dict[str, Any]:
        try:
            return self._client.get_schedule(Name=self._schedule_name)
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("scheduler", str(exc)) from exc
