from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import TeamHistory
from wolves_backend.team_history import team_history_points

router = APIRouter(prefix="/teams")

DepsDep = Annotated[Deps, Depends(get_deps)]


@router.get("/{team_id}/history")
async def history(team_id: str, deps: DepsDep, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> TeamHistory:
    refs = (await deps.snapshots.index())[:limit]
    bodies = await asyncio.gather(*(deps.storage.read(ref.key) for ref in refs))
    points = team_history_points(team_id, zip(refs, bodies, strict=True))
    if not points:
        raise HTTPException(status_code=404, detail="no forecast history for team")
    return TeamHistory(team_id=team_id, points=points)
