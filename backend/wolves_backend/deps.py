from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

# Request must be importable at runtime: FastAPI resolves the get_deps
# annotation when wiring the dependency.
from fastapi import Request  # noqa: TC002

from wolves.config import Settings as EngineSettings
from wolves_backend.clients.bucket import Bucket
from wolves_backend.clients.engine_tasks import EngineTasks
from wolves_backend.clients.run_index import RunIndex
from wolves_backend.clients.run_schedule import RunSchedule
from wolves_backend.impact_report import ImpactService
from wolves_backend.sim import EngineService
from wolves_backend.snapshots import SnapshotSource
from wolves_backend.storage import Storage

if TYPE_CHECKING:
    from wolves_backend.config import Settings


@dataclass
class Deps:
    storage: Storage
    snapshots: SnapshotSource
    run_index: RunIndex
    schedule: RunSchedule
    engine_tasks: EngineTasks
    engine: EngineService
    impact: ImpactService


def build_deps(settings: Settings) -> Deps:
    bucket = Bucket(bucket=settings.bucket, region=settings.aws_region) if settings.bucket else None
    storage = Storage(bucket=bucket, local_dir=settings.storage_dir)
    return Deps(
        storage=storage,
        snapshots=SnapshotSource(storage),
        run_index=RunIndex(
            table_name=settings.dynamo_table,
            region=settings.aws_region,
            endpoint_url=settings.dynamo_endpoint or None,
        ),
        schedule=RunSchedule(schedule_name=settings.schedule_name, region=settings.aws_region),
        engine_tasks=EngineTasks(
            cluster_arn=settings.ecs_cluster_arn,
            task_definition=settings.ecs_task_definition,
            extra_task_families=(settings.ecs_agent_task_definition,),
            subnets=settings.subnet_ids,
            security_group=settings.ecs_security_group,
            region=settings.aws_region,
        ),
        engine=EngineService(EngineSettings()),
        impact=ImpactService(),
    )


def get_deps(request: Request) -> Deps:
    return request.app.state.deps
