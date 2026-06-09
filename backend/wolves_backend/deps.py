from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

# Request must be importable at runtime: FastAPI resolves the get_deps
# annotation when wiring the dependency.
from fastapi import Request

from wolves_backend.clients.engine_tasks import EngineTasks
from wolves_backend.clients.run_index import RunIndex
from wolves_backend.clients.run_schedule import RunSchedule
from wolves_backend.clients.snapshot_bucket import SnapshotBucket
from wolves_backend.snapshots import SnapshotSource

if TYPE_CHECKING:
    from wolves_backend.config import Settings


@dataclass
class Deps:
    snapshots: SnapshotSource
    run_index: RunIndex
    schedule: RunSchedule
    engine_tasks: EngineTasks


def build_deps(settings: Settings) -> Deps:
    bucket = (
        SnapshotBucket(bucket=settings.snapshot_bucket, region=settings.aws_region)
        if settings.snapshot_bucket
        else None
    )
    return Deps(
        snapshots=SnapshotSource(bucket=bucket, local_dir=settings.snapshot_dir),
        run_index=RunIndex(
            table_name=settings.dynamo_table,
            region=settings.aws_region,
            endpoint_url=settings.dynamo_endpoint or None,
        ),
        schedule=RunSchedule(schedule_name=settings.schedule_name, region=settings.aws_region),
        engine_tasks=EngineTasks(
            cluster_arn=settings.ecs_cluster_arn,
            task_definition=settings.ecs_task_definition,
            subnets=settings.subnet_ids,
            security_group=settings.ecs_security_group,
            region=settings.aws_region,
        ),
    )


def get_deps(request: Request) -> Deps:
    return request.app.state.deps
