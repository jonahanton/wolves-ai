from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from wolves.data.store import DatasetNotFoundError

# TC001: FastAPI resolves response annotations at runtime.
from wolves.insights.explain import StrengthExplanation  # noqa: TC001
from wolves.insights.path_tree import PathTree  # noqa: TC001
from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import TeamHistories, TeamHistory
from wolves_backend.team_history import team_histories_points

logger = logging.getLogger(__name__)

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
    t0 = time.monotonic()
    refs = (await deps.snapshots.index())[:limit]
    t_index = time.monotonic()
    bodies = list(await asyncio.gather(*(deps.storage.read(ref.key) for ref in refs)))
    t_reads = time.monotonic()
    snapshots = list(zip(refs, bodies, strict=True))
    # JSON parsing dominates here; keep it off the API event loop.
    series = await asyncio.to_thread(team_histories_points, team_ids, snapshots)
    t_parse = time.monotonic()
    logger.info(
        "histories timing: teams=%d snapshots=%d agents=%d missing_bodies=%d empty_series=%d "
        "index_ms=%.0f reads_ms=%.0f parse_ms=%.0f total_ms=%.0f",
        len(team_ids),
        len(refs),
        sum(1 for ref in refs if ref.kind == "agent"),
        sum(1 for body in bodies if body is None),
        sum(1 for points in series.values() if not points),
        (t_index - t0) * 1000,
        (t_reads - t_index) * 1000,
        (t_parse - t_reads) * 1000,
        (t_parse - t0) * 1000,
    )
    return TeamHistories(histories=[TeamHistory(team_id=team_id, points=series[team_id]) for team_id in team_ids])


@router.get("/{team_id}/history")
async def history(team_id: str, deps: DepsDep, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> TeamHistory:
    refs = (await deps.snapshots.index())[:limit]
    bodies = await asyncio.gather(*(deps.storage.read(ref.key) for ref in refs))
    snapshots = list(zip(refs, bodies, strict=True))
    points = (await asyncio.to_thread(team_histories_points, [team_id], snapshots))[team_id]
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
