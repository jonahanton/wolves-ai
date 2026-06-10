"""Fake boto3 clients injected at the adapter boundary, plus an app builder.
No test in this suite may construct a real boto3 client or touch AWS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from botocore.exceptions import ClientError

from wolves_backend.clients.engine_tasks import EngineTasks
from wolves_backend.clients.run_index import RunIndex
from wolves_backend.clients.run_schedule import RunSchedule
from wolves_backend.clients.snapshot_bucket import SnapshotBucket
from wolves_backend.config import Settings
from wolves_backend.deps import Deps
from wolves_backend.main import create_app
from wolves_backend.snapshots import SnapshotSource


class FakeBody:
    def __init__(self, content: str) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content.encode("utf-8")


class FakeS3Client:
    def __init__(self, objects: dict[str, str] | None = None) -> None:
        self.objects = objects or {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": FakeBody(self.objects[Key])}


class FakeDynamoTable:
    def __init__(self, run_items: list[dict[str, Any]] | None = None) -> None:
        self.run_items = run_items or []
        self.put_items: list[dict[str, Any]] = []

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.last_query = kwargs
        return {"Items": self.run_items[: kwargs["Limit"]]}

    def put_item(self, *, Item: dict[str, Any]) -> None:
        self.put_items.append(Item)


class FakeSchedulerClient:
    def __init__(self, *, state: str = "ENABLED", cron: str = "cron(0 11 * * ? *)") -> None:
        self.schedule: dict[str, Any] = {
            "Name": "wolves-daily-run",
            "GroupName": "default",
            "ScheduleExpression": cron,
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "Target": {"Arn": "arn:aws:ecs:eu-west-2:000000000000:cluster/wolves"},
            "State": state,
        }
        self.updates: list[dict[str, Any]] = []

    def get_schedule(self, *, Name: str) -> dict[str, Any]:
        return dict(self.schedule)

    def update_schedule(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)
        self.schedule["State"] = kwargs["State"]


class FakeEcsClient:
    def __init__(self, *, task_arn: str | None = None, failure_reason: str | None = None) -> None:
        self.task_arn = task_arn
        self.failure_reason = failure_reason
        self.run_calls: list[dict[str, Any]] = []
        self.stop_calls: list[dict[str, Any]] = []

    def run_task(self, **kwargs: Any) -> dict[str, Any]:
        self.run_calls.append(kwargs)
        if self.task_arn is None:
            return {"tasks": [], "failures": [{"reason": self.failure_reason or "unknown"}]}
        return {"tasks": [{"taskArn": self.task_arn}]}

    def stop_task(self, **kwargs: Any) -> None:
        self.stop_calls.append(kwargs)


def build_test_app(
    *,
    snapshot_dir: Path | None = None,
    s3: FakeS3Client | None = None,
    dynamo: FakeDynamoTable | None = None,
    scheduler: FakeSchedulerClient | None = None,
    ecs: FakeEcsClient | None = None,
    environment: str = "local",
    admin_dev_bypass: bool = False,
) -> Any:
    settings = Settings(
        _env_file=None,
        environment=environment,
        admin_dev_bypass=admin_dev_bypass,
        snapshot_bucket="test-bucket" if s3 is not None else "",
        snapshot_dir=snapshot_dir or Path("/nonexistent"),
        ecs_subnets="subnet-1,subnet-2",
        ecs_security_group="sg-1",
        ecs_cluster_arn="arn:aws:ecs:eu-west-2:000000000000:cluster/wolves",
    )
    bucket = SnapshotBucket(bucket="test-bucket", region="eu-west-2", client=s3) if s3 is not None else None
    deps = Deps(
        snapshots=SnapshotSource(bucket=bucket, local_dir=settings.snapshot_dir),
        run_index=RunIndex(table_name="t", region="eu-west-2", table=dynamo or FakeDynamoTable()),
        schedule=RunSchedule(
            schedule_name="wolves-daily-run", region="eu-west-2", client=scheduler or FakeSchedulerClient()
        ),
        engine_tasks=EngineTasks(
            cluster_arn=settings.ecs_cluster_arn,
            task_definition=settings.ecs_task_definition,
            subnets=settings.subnet_ids,
            security_group=settings.ecs_security_group,
            region="eu-west-2",
            client=ecs or FakeEcsClient(task_arn="arn:aws:ecs:eu-west-2:000000000000:task/wolves/abc123"),
        ),
    )
    return create_app(settings, deps=deps)


def client_for(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
