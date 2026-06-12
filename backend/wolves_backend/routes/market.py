from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

# TC001: FastAPI resolves response annotations at runtime.
from wolves.insights.implied_reach import ImpliedReachSeries  # noqa: TC001
from wolves.insights.market_gaps import MarketGaps  # noqa: TC001
from wolves_backend.deps import Deps, get_deps

router = APIRouter(prefix="/market")

DepsDep = Annotated[Deps, Depends(get_deps)]


@router.get("/gaps")
async def gaps(deps: DepsDep) -> MarketGaps:
    return await deps.engine.market_gaps()


@router.get("/reach")
async def reach(deps: DepsDep) -> ImpliedReachSeries:
    series = await deps.engine.market_reach()
    if not series.points:
        raise HTTPException(status_code=404, detail="no market snapshots held")
    return series
