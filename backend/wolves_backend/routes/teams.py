from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from wolves.data.store import DatasetNotFoundError

# FastAPI resolves response annotations at runtime, so these stay real imports.
from wolves.insights.explain import StrengthExplanation  # noqa: TC001
from wolves.insights.path_tree import PathTree  # noqa: TC001
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


@router.get("/{team_id}/paths")
async def paths(team_id: str, deps: DepsDep, view: Literal["reach", "title"] = "reach") -> PathTree:
    try:
        return await deps.engine.team_paths(team_id, view=view)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"{team_id} is not a tournament team") from exc


@router.get("/{team_id}/explain")
async def explain(team_id: str, deps: DepsDep) -> StrengthExplanation:
    try:
        return await deps.engine.team_explain(team_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"{team_id} is not a tournament team") from exc
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=503, detail="the research dataset is not available here") from exc
