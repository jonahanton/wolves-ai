from __future__ import annotations

import time

from fastapi import APIRouter

from wolves_backend.models import Health

router = APIRouter()

_start_time = time.monotonic()


@router.get("/healthz")
async def healthz() -> Health:
    return Health(status="ok", uptime_s=round(time.monotonic() - _start_time, 1))
