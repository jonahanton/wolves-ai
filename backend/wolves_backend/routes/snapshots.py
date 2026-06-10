from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from wolves_backend.deps import Deps, get_deps
from wolves_backend.snapshots import is_valid_run_id

router = APIRouter(prefix="/snapshots")


def _json_response(raw: str) -> Response:
    return Response(content=raw, media_type="application/json")


@router.get("/latest")
async def latest(deps: Annotated[Deps, Depends(get_deps)]) -> Response:
    raw = await deps.snapshots.read_latest()
    if raw is None:
        raise HTTPException(status_code=404, detail="no snapshot available")
    return _json_response(raw)


@router.get("/{run_id}")
async def by_id(run_id: str, deps: Annotated[Deps, Depends(get_deps)]) -> Response:
    if not is_valid_run_id(run_id):
        raise HTTPException(status_code=400, detail="invalid run id")
    raw = await deps.snapshots.read(run_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return _json_response(raw)
