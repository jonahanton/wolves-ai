from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wolves.config import Settings
from wolves.live import _started_results
from wolves.sim.format import PlayedResult, load_format

FMT = load_format(Settings().data_dir)


@pytest.mark.parametrize(
    ("now", "kept"),
    [
        (datetime(2026, 6, 12, 11, 18, tzinfo=UTC), False),
        (datetime(2026, 6, 21, 0, 0, tzinfo=UTC), True),
    ],
)
def test_result_before_scheduled_kickoff_is_dropped(now: datetime, kept: bool):
    # Match 29 is scheduled for 20 June 2026; a provider score arriving before
    # then is corrupt and must not reach the results store.
    overlay = {29: PlayedResult(match=29, home_goals=3, away_goals=0)}

    started = _started_results(FMT, overlay, now=now)

    assert (29 in started) is kept
