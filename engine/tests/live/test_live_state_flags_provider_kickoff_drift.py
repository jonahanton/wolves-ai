from __future__ import annotations

from datetime import UTC, datetime

from tests.live.live_fakes import FakeLiveForecaster, live_fixture
from wolves.live_state import build_live_state

FETCHED = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)


def test_moved_kickoff_is_flagged_against_the_schedule() -> None:
    moved = live_fixture(status="scheduled", goals=(None, None), elapsed=None, day="2026-06-11T19:30:00+00:00")

    state = build_live_state(FakeLiveForecaster(), [moved], fetched_at=FETCHED, results={}, previous=None, n_sims=200)

    assert [d.match for d in state.schedule_drift] == [1]
    assert state.schedule_drift[0].scheduled_kickoff == "2026-06-11T19:00:00Z"
    assert state.schedule_drift[0].provider_kickoff == "2026-06-11T19:30:00+00:00"


def test_matching_kickoff_reports_no_drift() -> None:
    state = build_live_state(
        FakeLiveForecaster(),
        [live_fixture(status="scheduled", goals=(None, None), elapsed=None)],
        fetched_at=FETCHED,
        results={},
        previous=None,
        n_sims=200,
    )

    assert state.schedule_drift == []
