from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

from wolves_backend.errors import UpstreamError
from wolves_backend.models import RunRecord

RUN_PK = "RUN"
CONTROL_PK = "CONTROL"
RUN_ENABLED_SK = "run_enabled"


class RunIndex:
    """DynamoDB index of engine runs plus the run_enabled control item."""

    def __init__(
        self, *, table_name: str, region: str, endpoint_url: str | None = None, table: Any | None = None
    ) -> None:
        self._table = table or boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint_url).Table(
            table_name
        )

    def list_runs(self, *, limit: int = 50) -> list[RunRecord]:
        """Return the most recent runs, newest first."""
        try:
            response = self._table.query(
                KeyConditionExpression=Key("PK").eq(RUN_PK),
                ScanIndexForward=False,
                Limit=limit,
            )
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("dynamodb", str(exc)) from exc
        return [_to_record(item) for item in response["Items"]]

    def set_run_enabled(self, *, enabled: bool) -> None:
        """Write the kill-switch flag the daily task checks at start."""
        try:
            self._table.put_item(Item={"PK": CONTROL_PK, "SK": RUN_ENABLED_SK, "enabled": enabled})
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("dynamodb", str(exc)) from exc

    def put_audit(self, item: dict[str, Any]) -> None:
        try:
            self._table.put_item(Item=item)
        except (ClientError, BotoCoreError) as exc:
            raise UpstreamError("dynamodb", str(exc)) from exc


def _to_record(item: dict[str, Any]) -> RunRecord:
    return RunRecord(
        run_id=str(item.get("run_id", "")),
        created_at=str(item.get("created_at", "")),
        s3_key=str(item.get("s3_key", "")),
        status="failed" if item.get("status") == "failed" else "completed",
        cost=float(item.get("cost", 0)),
        duration_s=float(item.get("duration_s", 0)),
        kind=str(item.get("kind", "")),
    )
