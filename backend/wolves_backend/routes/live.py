from __future__ import annotations

import hashlib
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from wolves.live_state import LiveState
from wolves.s3.layout import LIVE_STATE
from wolves_backend.deps import Deps, get_deps
from wolves_backend.live_history import DATE_PATTERN, day_states
from wolves_backend.models import LiveHistory, LiveHistoryFixture, LiveHistoryPoint
from wolves_backend.sim import Pin

router = APIRouter(prefix="/live")

logger = logging.getLogger(__name__)

DepsDep = Annotated[Deps, Depends(get_deps)]

LIVE_STATE_KEY = LIVE_STATE.key()


def _held_pins(state: LiveState) -> list[Pin]:
    return [
        Pin(match=f.match, home_goals=f.home_goals, away_goals=f.away_goals)
        for f in state.fixtures
        if f.status == "live" and f.match is not None and f.home_goals is not None and f.away_goals is not None
    ]


@router.get("", response_model=LiveState)
async def state(request: Request, deps: DepsDep) -> Response:
    raw = await deps.storage.read(LIVE_STATE_KEY)
    if raw is None:
        raise HTTPException(status_code=404, detail="no live state available")
    try:
        live = LiveState.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="live state is malformed") from exc
    # Always re-serialised compactly so the ETag is stable across engine readiness.
    payload = json.loads(raw)
    held = _held_pins(live)
    if held and deps.engine.ready:
        # Scores-hold is garnish; a sim failure must never take down /live.
        try:
            payload["scores_hold"] = await deps.engine.scores_hold(held, n_sims=deps.engine.settings.n_sims)
        except Exception:
            logger.exception("scores-hold failed; serving the raw live state")
    body = json.dumps(payload, separators=(",", ":"))
    etag = f'"{hashlib.md5(body.encode("utf-8")).hexdigest()}"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.get("/history/{date}")
async def history(date: str, deps: DepsDep) -> LiveHistory:
    if not DATE_PATTERN.fullmatch(date):
        raise HTTPException(status_code=400, detail="invalid date")
    states = await day_states(deps.storage, date)
    if not states:
        raise HTTPException(status_code=404, detail="no live history for date")
    return LiveHistory(date=date, points=[_thin(state) for state in states])


def _thin(state: LiveState) -> LiveHistoryPoint:
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
