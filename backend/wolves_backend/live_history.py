"""Read one day of immutable live-state polls, evenly sampled."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from pydantic import ValidationError

from wolves.live_state import LiveState

if TYPE_CHECKING:
    from wolves_backend.storage import Storage

LIVE_HISTORY_PREFIX = "live/history/"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Evenly sampling a long day keeps a series' shape at a fraction of the bytes.
MAX_HISTORY_POINTS = 360


def sample(keys: list[str], bound: int) -> list[str]:
    if len(keys) <= bound:
        return keys
    step = len(keys) / bound
    sampled = [keys[int(i * step)] for i in range(bound)]
    sampled[-1] = keys[-1]
    return sampled


async def day_states(storage: Storage, date: str, *, bound: int = MAX_HISTORY_POINTS) -> list[LiveState]:
    keys = sorted(await storage.list_keys(f"{LIVE_HISTORY_PREFIX}{date}/"))
    bodies = await asyncio.gather(*(storage.read(key) for key in sample(keys, bound)))
    states = []
    for body in bodies:
        if body is None:
            continue
        try:
            states.append(LiveState.model_validate_json(body))
        except ValidationError:
            continue
    return states
