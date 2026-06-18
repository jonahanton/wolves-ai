from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from wolves.data.store import DatasetNotFoundError

# TC001: FastAPI resolves response annotations at runtime.
from wolves.insights.explain import StrengthExplanation  # noqa: TC001
from wolves.insights.path_tree import PathTree  # noqa: TC001
from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import TeamHistories, TeamHistory
from wolves_backend.team_history import team_history_points

router = APIRouter(prefix="/teams")

DepsDep = Annotated[Deps, Depends(get_deps)]

MAX_HISTORY_IDS = 48


@router.get("/histories")
async def histories(
    deps: DepsDep,
    ids: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> TeamHistories:
    """Forecast series for several teams from one pass over the snapshot bodies."""
    team_ids = [team_id for team_id in (raw.strip() for raw in ids.split(",")) if team_id][:MAX_HISTORY_IDS]
    if not team_ids:
        raise HTTPException(status_code=400, detail="ids must list at least one team")
    refs = (await deps.snapshots.index())[:limit]
    bodies = list(await asyncio.gather(*(deps.storage.read(ref.key) for ref in refs)))
    snapshots = list(zip(refs, bodies, strict=True))
    return TeamHistories(
        histories=[
            TeamHistory(team_id=team_id, points=team_history_points(team_id, snapshots)) for team_id in team_ids
        ]
    )


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
