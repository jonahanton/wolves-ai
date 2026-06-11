from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import LiveState

router = APIRouter(prefix="/live")

DepsDep = Annotated[Deps, Depends(get_deps)]

LIVE_STATE_KEY = "live/state.json"


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
