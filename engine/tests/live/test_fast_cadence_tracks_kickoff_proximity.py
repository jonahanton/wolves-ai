from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.live.live_fakes import live_fixture
from wolves.live import _fast_cadence

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("status", "kickoff", "fast"),
    [
        ("live", NOW, True),
        ("scheduled", NOW + timedelta(minutes=30), True),
        ("scheduled", NOW - timedelta(minutes=30), True),
        ("scheduled", NOW + timedelta(hours=5), False),
        ("finished", NOW - timedelta(hours=2), False),
    ],
)
def test_fast_cadence_only_near_a_kickoff(status: str, kickoff: datetime, fast: bool) -> None:
    fixture = live_fixture(status=status, day=kickoff.isoformat())
    assert _fast_cadence([fixture], now=NOW) is fast


def test_idle_when_no_fixtures() -> None:
    assert _fast_cadence([], now=NOW) is False
