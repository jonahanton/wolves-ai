from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from wolves_backend.audit import build_audit_item
from wolves_backend.auth import require_admin
from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import (
    ActiveRuns,
    RunNowRequest,
    RunPolicy,
    RunStarted,
    ScheduleState,
    ScheduleUpdate,
    StopRequest,
    StopResult,
)
from wolves_backend.schedule import apply_schedule_update

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

DepsDep = Annotated[Deps, Depends(get_deps)]

RUN_COMMANDS = {
    "daily": ["wolves.run"],
    "agent": ["wolves.run_agent", "--live", "--confirm-spend"],
    "live": ["wolves.live", "--loop", "--interval", "60"],
}


async def _audit(deps: Deps, request: Request, *, action: str, payload: dict[str, Any]) -> None:
    source_ip = request.client.host if request.client else None
    item = build_audit_item(action=action, source_ip=source_ip, payload=payload)
    await asyncio.to_thread(deps.run_index.put_audit, item)


@router.get("/schedule")
async def schedule_state(deps: DepsDep) -> ScheduleState:
    return await asyncio.to_thread(lambda: deps.schedule.state())


@router.post("/schedule")
async def update_schedule(update: ScheduleUpdate, request: Request, deps: DepsDep) -> ScheduleState:
    state = await asyncio.to_thread(
        lambda: apply_schedule_update(deps.schedule, deps.run_index, enabled=update.enabled, cron=update.cron)
    )
    await _audit(deps, request, action="schedule-update", payload=update.model_dump(by_alias=True))
    return state


@router.get("/run-policy")
async def run_policy(deps: DepsDep) -> RunPolicy:
    return RunPolicy.model_validate(await deps.engine.run_policy())


@router.get("/runs/active")
async def active_runs(deps: DepsDep) -> ActiveRuns:
    return ActiveRuns(tasks=await asyncio.to_thread(deps.engine_tasks.list_active))


@router.post("/run-now", status_code=202)
async def run_now(request: Request, deps: DepsDep, body: RunNowRequest | None = None) -> RunStarted:
    body = body or RunNowRequest()
    force = body.force
    if not force and await asyncio.to_thread(deps.engine_tasks.list_active):
        raise HTTPException(status_code=409, detail="an engine run is already active; pass force to start another")
    environment = (
        {"AGENT_RUN_CEILING_USD": f"{body.ceiling_usd:.2f}"}
        if body.mode == "agent" and body.ceiling_usd is not None
        else None
    )
    task_arn = await asyncio.to_thread(
        deps.engine_tasks.run_now, command=RUN_COMMANDS[body.mode], environment=environment
    )
    await _audit(
        deps,
        request,
        action="run-now",
        payload={"taskArn": task_arn, "force": force, "mode": body.mode, "ceilingUsd": body.ceiling_usd},
    )
    return RunStarted(task_arn=task_arn)


@router.post("/stop")
async def stop(body: StopRequest, request: Request, deps: DepsDep) -> StopResult:
    await asyncio.to_thread(deps.engine_tasks.stop, body.task_arn)
    await _audit(deps, request, action="stop", payload={"taskArn": body.task_arn})
    return StopResult(stopped=body.task_arn)
