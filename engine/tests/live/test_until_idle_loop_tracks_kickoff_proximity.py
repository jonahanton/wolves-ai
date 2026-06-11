from __future__ import annotations

from datetime import UTC, datetime, timedelta

from wolves.live import near_kickoff
from wolves.live_state import LiveFixture, LiveState

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _state(*fixtures: LiveFixture) -> LiveState:
    stamp = NOW.isoformat(timespec="seconds")
    return LiveState(generated_at=stamp, fetched_at=stamp, stale_after=stamp, fixtures=list(fixtures))


def _fixture(status: str, kickoff: datetime) -> LiveFixture:
    return LiveFixture(
        external_id=1,
        match=1,
        status=status,
        kickoff=kickoff.isoformat(),
        home_name="Mexico",
        away_name="South Africa",
    )


def test_live_fixture_keeps_the_loop_running() -> None:
    state = _state(_fixture("live", NOW - timedelta(hours=1)))

    assert near_kickoff(state, now=NOW, horizon=timedelta(hours=6))


def test_upcoming_and_delayed_kickoffs_count_as_near() -> None:
    upcoming = _state(_fixture("scheduled", NOW + timedelta(hours=5)))
    delayed = _state(_fixture("scheduled", NOW - timedelta(minutes=30)))

    assert near_kickoff(upcoming, now=NOW, horizon=timedelta(hours=6))
    assert near_kickoff(delayed, now=NOW, horizon=timedelta(hours=6))


def test_finished_day_with_distant_next_kickoff_is_idle() -> None:
    state = _state(
        _fixture("finished", NOW - timedelta(hours=3)),
        _fixture("scheduled", NOW + timedelta(hours=10)),
    )

    assert not near_kickoff(state, now=NOW, horizon=timedelta(hours=6))
    assert not near_kickoff(None, now=NOW, horizon=timedelta(hours=6))
