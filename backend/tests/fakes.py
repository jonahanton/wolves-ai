"""Fake boto3 clients injected at the adapter boundary, plus an app builder.
No test in this suite may construct a real boto3 client or touch AWS."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from botocore.exceptions import ClientError

from wolves_backend.clients.bucket import Bucket
from wolves_backend.clients.engine_tasks import EngineTasks
from wolves_backend.clients.run_index import RunIndex
from wolves_backend.clients.run_schedule import RunSchedule
from wolves_backend.config import Settings
from wolves_backend.deps import Deps
from wolves_backend.main import create_app
from wolves_backend.snapshots import SnapshotSource
from wolves_backend.storage import Storage

ADMIN_TOKEN = "test-admin-token"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


class FakeBody:
    def __init__(self, content: str) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content.encode("utf-8")


class FakePaginator:
    def __init__(self, objects: dict[str, str]) -> None:
        self._objects = objects

    def paginate(self, *, Bucket: str, Prefix: str) -> Any:
        yield {"Contents": [{"Key": key} for key in sorted(self._objects) if key.startswith(Prefix)]}


class FakeS3Client:
    def __init__(self, objects: dict[str, str] | None = None) -> None:
        self.objects = objects or {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": FakeBody(self.objects[Key])}

    def get_paginator(self, name: str) -> FakePaginator:
        return FakePaginator(self.objects)


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
    def __init__(
        self,
        *,
        task_arn: str | None = None,
        failure_reason: str | None = None,
        active_tasks: list[dict[str, Any]] | None = None,
    ) -> None:
        self.task_arn = task_arn
        self.failure_reason = failure_reason
        self.active_tasks = active_tasks or []
        self.run_calls: list[dict[str, Any]] = []
        self.stop_calls: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []

    def run_task(self, **kwargs: Any) -> dict[str, Any]:
        self.run_calls.append(kwargs)
        if self.task_arn is None:
            return {"tasks": [], "failures": [{"reason": self.failure_reason or "unknown"}]}
        return {"tasks": [{"taskArn": self.task_arn}]}

    def stop_task(self, **kwargs: Any) -> None:
        self.stop_calls.append(kwargs)

    def list_tasks(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return {"taskArns": [task["taskArn"] for task in self.active_tasks]}

    def describe_tasks(self, **kwargs: Any) -> dict[str, Any]:
        return {"tasks": [dict(task) for task in self.active_tasks]}


def build_test_app(
    *,
    storage_dir: Path | None = None,
    s3: FakeS3Client | None = None,
    dynamo: FakeDynamoTable | None = None,
    scheduler: FakeSchedulerClient | None = None,
    ecs: FakeEcsClient | None = None,
    environment: str = "local",
    admin_token: str = ADMIN_TOKEN,
) -> Any:
    settings = Settings(
        _env_file=None,
        environment=environment,
        admin_token=admin_token,
        bucket="test-bucket" if s3 is not None else "",
        storage_dir=storage_dir or Path("/nonexistent"),
        ecs_subnets="subnet-1,subnet-2",
        ecs_security_group="sg-1",
        ecs_cluster_arn="arn:aws:ecs:eu-west-2:000000000000:cluster/wolves",
    )
    bucket = Bucket(bucket="test-bucket", region="eu-west-2", client=s3) if s3 is not None else None
    storage = Storage(bucket=bucket, local_dir=settings.storage_dir)
    deps = Deps(
        storage=storage,
        snapshots=SnapshotSource(storage),
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


def client_for(app: Any, *, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers)
