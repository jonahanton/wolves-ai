from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolves_backend.clients.run_index import RunIndex
    from wolves_backend.clients.run_schedule import RunSchedule
    from wolves_backend.models import ScheduleState


def apply_schedule_update(
    schedule: RunSchedule, run_index: RunIndex, *, enabled: bool, cron: str | None = None
) -> ScheduleState:
    """Flip both layers of the kill switch: the schedule itself and the
    run_enabled flag the daily task checks at start, so disabling also stops
    a run the schedule has already launched."""
    state = schedule.update(enabled=enabled, cron=cron)
    run_index.set_run_enabled(enabled=enabled)
    return state
