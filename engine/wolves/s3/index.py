"""DynamoDB index of runs and the run_enabled kill switch."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

from wolves.s3.records import RunRecord, RunStatus

if TYPE_CHECKING:
    from collections.abc import Callable

RUN_PK = "RUN"
CONTROL_PK = "CONTROL"
RUN_ENABLED_SK = "run_enabled"


class RunIndexUnavailableError(Exception):
    """The DynamoDB table could not be reached or queried."""

    def __init__(self, table_name: str, endpoint: str | None) -> None:
        self.table_name = table_name
        self.endpoint = endpoint
        super().__init__(f"run index table {table_name!r} unavailable (endpoint={endpoint or 'aws'})")


class RunIndex:
    """Single-table index of runs plus the run_enabled control item."""

    def __init__(self, *, table_name: str, region: str, endpoint_url: str | None = None) -> None:
        self._table_name = table_name
        self._endpoint = endpoint_url
        self._table = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint_url).Table(table_name)

    def run_enabled(self) -> bool:
        """Read the kill-switch flag; a missing control item means enabled."""
        response = self._guard(lambda: self._table.get_item(Key={"PK": CONTROL_PK, "SK": RUN_ENABLED_SK}))
        item = response.get("Item")
        return bool(item["enabled"]) if item else True

    def set_run_enabled(self, *, enabled: bool) -> None:
        """Write the kill-switch flag."""
        self._guard(lambda: self._table.put_item(Item={"PK": CONTROL_PK, "SK": RUN_ENABLED_SK, "enabled": enabled}))

    def record_run(self, record: RunRecord) -> None:
        """Index a run, replacing any earlier item for the same run_id."""
        for item in self._run_items():
            if item["run_id"] == record.run_id and item["SK"] != record.created_at:
                self._guard(lambda sk=item["SK"]: self._table.delete_item(Key={"PK": RUN_PK, "SK": sk}))
        self._guard(
            lambda: self._table.put_item(
                Item={
                    "PK": RUN_PK,
                    "SK": record.created_at,
                    "run_id": record.run_id,
                    "created_at": record.created_at,
                    "s3_key": record.s3_key,
                    "status": record.status,
                    "cost": Decimal(str(record.cost)),
                    "duration_s": Decimal(str(record.duration_s)),
                    "kind": record.kind,
                }
            )
        )

    def list_runs(self, *, limit: int = 50) -> list[RunRecord]:
        """Return the most recent runs, newest first."""
        return [_to_record(item) for item in self._run_items(newest_first=True)[:limit]]

    def _run_items(self, *, newest_first: bool = False) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        exclusive_start_key: dict[str, Any] | None = None
        while True:
            response = self._guard(
                lambda start_key=exclusive_start_key: self._table.query(
                    KeyConditionExpression=Key("PK").eq(RUN_PK),
                    ScanIndexForward=not newest_first,
                    **({"ExclusiveStartKey": start_key} if start_key else {}),
                )
            )
            items.extend(response["Items"])
            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                return items

    def _guard[T](self, call: Callable[[], T]) -> T:
        try:
            return call()
        except (ClientError, BotoCoreError) as exc:
            raise RunIndexUnavailableError(self._table_name, self._endpoint) from exc


def _to_record(item: dict[str, Any]) -> RunRecord:
    status: RunStatus = "failed" if item["status"] == "failed" else "completed"
    return RunRecord(
        run_id=str(item["run_id"]),
        created_at=str(item["created_at"]),
        s3_key=str(item["s3_key"]),
        status=status,
        cost=float(item["cost"]),
        duration_s=float(item["duration_s"]),
        kind=str(item["kind"]),
    )
