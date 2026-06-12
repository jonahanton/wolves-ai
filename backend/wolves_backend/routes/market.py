from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

# TC001: FastAPI resolves response annotations at runtime.
from wolves.insights.market_gaps import MarketGaps  # noqa: TC001
from wolves_backend.deps import Deps, get_deps

router = APIRouter(prefix="/market")

DepsDep = Annotated[Deps, Depends(get_deps)]


@router.get("/gaps")
async def gaps(deps: DepsDep) -> MarketGaps:
    return await deps.engine.market_gaps()
