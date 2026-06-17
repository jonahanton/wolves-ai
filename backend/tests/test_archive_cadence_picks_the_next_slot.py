from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wolves_backend.jobs import next_archive_time

HOURS = (8, 14, 18, 22)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 6, 12, 7, 59, tzinfo=UTC), datetime(2026, 6, 12, 8, tzinfo=UTC)),
        (datetime(2026, 6, 12, 8, 0, tzinfo=UTC), datetime(2026, 6, 12, 14, tzinfo=UTC)),
        (datetime(2026, 6, 12, 21, 30, tzinfo=UTC), datetime(2026, 6, 12, 22, tzinfo=UTC)),
        (datetime(2026, 6, 12, 22, 0, 1, tzinfo=UTC), datetime(2026, 6, 13, 8, tzinfo=UTC)),
    ],
)
def test_next_slot_is_strictly_after_now_and_wraps_midnight(now, expected):
    assert next_archive_time(now, hours=HOURS) == expected
