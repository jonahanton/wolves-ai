from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import RunDetail, RunHistory
from wolves_backend.runs import (
    artifact_index_key,
    artifact_key,
    artifact_records,
    events_key,
    is_safe_id,
    journal_key,
    summarise_events,
)

router = APIRouter(prefix="/runs")

DepsDep = Annotated[Deps, Depends(get_deps)]


def _checked(run_id: str) -> str:
    if not is_safe_id(run_id):
        raise HTTPException(status_code=400, detail="invalid run id")
    return run_id


@router.get("")
async def list_runs(request: Request, deps: DepsDep) -> RunHistory:
    limit = request.app.state.settings.run_history_limit
    runs = await asyncio.to_thread(lambda: deps.run_index.list_runs(limit=limit))
    return RunHistory(runs=runs)


@router.get("/{run_id}")
async def detail(run_id: str, request: Request, deps: DepsDep) -> RunDetail:
    run_id = _checked(run_id)
    limit = request.app.state.settings.run_history_limit
    records, journal, events, index = await asyncio.gather(
        asyncio.to_thread(lambda: deps.run_index.list_runs(limit=limit)),
        deps.storage.read(journal_key(run_id)),
        deps.storage.read(events_key(run_id)),
        deps.storage.read(artifact_index_key(run_id)),
    )
    record = next((item for item in records if item.run_id == run_id), None)
    if record is None and journal is None and events is None and index is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunDetail(
        record=record,
        has_journal=journal is not None,
        events=summarise_events(events) if events is not None else None,
        artifacts=artifact_records(index) if index is not None else [],
    )


@router.get("/{run_id}/journal")
async def journal(run_id: str, deps: DepsDep) -> Response:
    raw = await deps.storage.read(journal_key(_checked(run_id)))
    if raw is None:
        raise HTTPException(status_code=404, detail="journal not found")
    return Response(content=raw, media_type="text/markdown; charset=utf-8")


@router.get("/{run_id}/events")
async def events(run_id: str, deps: DepsDep) -> Response:
    raw = await deps.storage.read(events_key(_checked(run_id)))
    if raw is None:
        raise HTTPException(status_code=404, detail="events not found")
    return Response(content=raw, media_type="application/x-ndjson")


@router.get("/{run_id}/artifacts/{artifact_id}")
async def artifact(run_id: str, artifact_id: str, deps: DepsDep) -> Response:
    if not is_safe_id(artifact_id):
        raise HTTPException(status_code=400, detail="invalid artifact id")
    raw = await deps.storage.read(artifact_key(_checked(run_id), artifact_id))
    if raw is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return Response(content=raw, media_type="application/json")
