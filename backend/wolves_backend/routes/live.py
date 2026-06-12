from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import LiveHistory, LiveHistoryFixture, LiveHistoryPoint, LiveState

router = APIRouter(prefix="/live")

DepsDep = Annotated[Deps, Depends(get_deps)]

LIVE_STATE_KEY = "live/state.json"
LIVE_HISTORY_PREFIX = "live/history/"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Evenly sampling a long day keeps the worm's shape at a fraction of the bytes.
MAX_HISTORY_POINTS = 360


@router.get("", response_model=LiveState)
async def state(request: Request, deps: DepsDep) -> Response:
    raw = await deps.storage.read(LIVE_STATE_KEY)
    if raw is None:
        raise HTTPException(status_code=404, detail="no live state available")
    try:
        LiveState.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="live state is malformed") from exc
    etag = f'"{hashlib.md5(raw.encode("utf-8")).hexdigest()}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=raw, media_type="application/json", headers=headers)


@router.get("/history/{date}")
async def history(date: str, deps: DepsDep) -> LiveHistory:
    if not DATE_PATTERN.fullmatch(date):
        raise HTTPException(status_code=400, detail="invalid date")
    keys = sorted(await deps.storage.list_keys(f"{LIVE_HISTORY_PREFIX}{date}/"))
    keys = _sample(keys, MAX_HISTORY_POINTS)
    if not keys:
        raise HTTPException(status_code=404, detail="no live history for date")
    bodies = await asyncio.gather(*(deps.storage.read(key) for key in keys))
    points = [point for body in bodies if body is not None if (point := _thin(body)) is not None]
    if not points:
        raise HTTPException(status_code=404, detail="no live history for date")
    return LiveHistory(date=date, points=points)


def _sample(keys: list[str], bound: int) -> list[str]:
    if len(keys) <= bound:
        return keys
    step = len(keys) / bound
    sampled = [keys[int(i * step)] for i in range(bound)]
    sampled[-1] = keys[-1]
    return sampled


def _thin(body: str) -> LiveHistoryPoint | None:
    try:
        state = LiveState.model_validate_json(body)
    except ValidationError:
        return None
    return LiveHistoryPoint(
        fetched_at=state.fetched_at,
        fixtures=[
            LiveHistoryFixture(
                external_id=fixture.external_id,
                match=fixture.match,
                status=fixture.status,
                minute=fixture.minute,
                home_goals=fixture.home_goals,
                away_goals=fixture.away_goals,
                forecast=fixture.forecast,
            )
            for fixture in state.fixtures
        ],
    )
