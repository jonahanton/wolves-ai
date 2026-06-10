from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from wolves_backend.deps import Deps, get_deps

router = APIRouter(prefix="/agent-state")

DepsDep = Annotated[Deps, Depends(get_deps)]

STATE_FILES = {
    "lessons": "lessons.jsonl",
    "scenarios": "scenarios.jsonl",
    "sources-seen": "sources_seen.jsonl",
    "relevance-feedback": "relevance_feedback.jsonl",
    "calibration": "calibration.jsonl",
}


@router.get("/{name}")
async def state(name: str, deps: DepsDep) -> Response:
    file = STATE_FILES.get(name)
    if file is None:
        raise HTTPException(status_code=404, detail="unknown agent state")
    raw = await deps.storage.read(f"agent-state/{file}")
    if raw is None:
        raise HTTPException(status_code=404, detail="agent state not found")
    return Response(content=raw, media_type="application/x-ndjson")
