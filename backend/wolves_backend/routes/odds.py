from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import OddsDates

router = APIRouter(prefix="/odds")

DepsDep = Annotated[Deps, Depends(get_deps)]

ARCHIVE_PREFIX = "odds-archive/"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SERIES_SUFFIX = ".series.json"


@router.get("/dates")
async def dates(deps: DepsDep) -> OddsDates:
    keys = await deps.storage.list_keys(ARCHIVE_PREFIX)
    days = {key.split("/")[1] for key in keys if key.count("/") >= 2}
    return OddsDates(dates=sorted(day for day in days if DATE_PATTERN.fullmatch(day)))


@router.get("/{date}")
async def series(date: str, deps: DepsDep) -> Response:
    if not DATE_PATTERN.fullmatch(date):
        raise HTTPException(status_code=400, detail="invalid date")
    keys = await deps.storage.list_keys(f"{ARCHIVE_PREFIX}{date}/")
    series_keys = sorted(key for key in keys if key.endswith(SERIES_SUFFIX))
    if not series_keys:
        raise HTTPException(status_code=404, detail="no odds for date")
    bodies = await asyncio.gather(*(deps.storage.read(key) for key in series_keys))
    points = [json.loads(body) for body in bodies if body is not None]
    return Response(content=json.dumps({"date": date, "points": points}), media_type="application/json")
