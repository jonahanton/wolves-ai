"""Estimated movement of the agent's published forecast, served from the precomputed report."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from wolves_backend.deps import Deps, get_deps
from wolves_backend.impact_report import MalformedAgentForecastError, NoAgentForecastError
from wolves_backend.models import Impact  # noqa: TC001  FastAPI resolves the return annotation at runtime

router = APIRouter()

DepsDep = Annotated[Deps, Depends(get_deps)]

CACHE_CONTROL = "public, s-maxage=15, stale-while-revalidate=30"


@router.get("/impact")
async def impact(deps: DepsDep, response: Response) -> Impact:
    try:
        report = await deps.impact.get(deps)
    except NoAgentForecastError as exc:
        raise HTTPException(status_code=404, detail="no agent forecast published") from exc
    except MalformedAgentForecastError as exc:
        raise HTTPException(status_code=502, detail="published agent forecast is malformed") from exc
    response.headers["Cache-Control"] = CACHE_CONTROL
    return report
