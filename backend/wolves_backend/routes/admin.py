from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from wolves_backend.auth import require_admin
from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import RunStarted, ScheduleState, ScheduleUpdate, StopRequest, StopResult
from wolves_backend.schedule import set_schedule_enabled

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

DepsDep = Annotated[Deps, Depends(get_deps)]


@router.get("/schedule")
async def schedule_state(deps: DepsDep) -> ScheduleState:
    return await asyncio.to_thread(lambda: deps.schedule.state())


@router.post("/schedule")
async def update_schedule(update: ScheduleUpdate, deps: DepsDep) -> ScheduleState:
    return await asyncio.to_thread(lambda: set_schedule_enabled(deps.schedule, deps.run_index, enabled=update.enabled))


@router.post("/run-now", status_code=202)
async def run_now(deps: DepsDep) -> RunStarted:
    task_arn = await asyncio.to_thread(deps.engine_tasks.run_now)
    return RunStarted(task_arn=task_arn)


@router.post("/stop")
async def stop(body: StopRequest, deps: DepsDep) -> StopResult:
    await asyncio.to_thread(deps.engine_tasks.stop, body.task_arn)
    return StopResult(stopped=body.task_arn)
