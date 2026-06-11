from __future__ import annotations

from datetime import UTC, datetime

from tests.live.live_fakes import FakeLiveForecaster, live_fixture
from wolves.live_state import build_live_state


def test_score_changes_move_in_match_forecast_and_title_probs() -> None:
    forecaster = FakeLiveForecaster()
    fetched_at = datetime(2026, 6, 11, 19, 30, tzinfo=UTC)

    level = build_live_state(
        forecaster,
        [live_fixture(goals=(0, 0))],
        fetched_at=fetched_at,
        results={},
        previous=None,
        n_sims=200,
    )
    leading = build_live_state(
        forecaster,
        [live_fixture(goals=(1, 0))],
        fetched_at=fetched_at,
        results={},
        previous=None,
        n_sims=200,
    )

    assert level.fixtures[0].forecast is not None
    assert leading.fixtures[0].forecast is not None
    assert leading.fixtures[0].forecast.p_home > level.fixtures[0].forecast.p_home
    assert leading.title_probs["mexico"] > level.title_probs["mexico"]


def test_live_state_covers_scheduled_finished_abandoned_no_data_and_concurrent_games() -> None:
    forecaster = FakeLiveForecaster()
    fetched_at = datetime(2026, 6, 11, 19, 30, tzinfo=UTC)
    fixtures = [
        live_fixture(status="scheduled", goals=(None, None), elapsed=None),
        live_fixture(status="finished", goals=(2, 0), elapsed=90),
        live_fixture(
            "Czechia", "South Africa", fixture_id=1300030, status="abandoned", goals=(None, None), elapsed=None
        ),
        live_fixture("South Korea", "Czechia", fixture_id=1300002, status="live", goals=(1, 1), elapsed=55),
        live_fixture("Mexico", "South Africa", fixture_id=1300003, status="live", goals=(1, 0), elapsed=70),
    ]

    state = build_live_state(forecaster, fixtures, fetched_at=fetched_at, results={}, previous=None, n_sims=200)
    empty = build_live_state(forecaster, [], fetched_at=fetched_at, results={}, previous=None, n_sims=200)

    by_status = {fixture.status: fixture for fixture in state.fixtures}
    assert state.live_match_count == 2
    assert by_status["scheduled"].forecast.source == "pre_match"
    assert by_status["finished"].forecast.source == "settled"
    assert by_status["abandoned"].forecast is None
    assert empty.fixtures == []
    assert empty.live_match_count == 0


def test_reversed_provider_order_uses_schedule_oriented_names() -> None:
    forecaster = FakeLiveForecaster()
    fixture = live_fixture(
        home="South Africa",
        away="Mexico",
        status="live",
        goals=(0, 1),
        elapsed=65,
    )

    state = build_live_state(
        forecaster,
        [fixture],
        fetched_at=datetime(2026, 6, 11, 19, 30, tzinfo=UTC),
        results={},
        previous=None,
        n_sims=200,
    )

    assert state.fixtures[0].home_name == "Mexico"
    assert state.fixtures[0].away_name == "South Africa"
    assert state.fixtures[0].home_goals == 1
    assert state.fixtures[0].away_goals == 0


def test_live_fixture_without_elapsed_time_has_no_in_match_forecast() -> None:
    forecaster = FakeLiveForecaster()

    state = build_live_state(
        forecaster,
        [live_fixture(goals=(0, 0), elapsed=None)],
        fetched_at=datetime(2026, 6, 11, 19, 30, tzinfo=UTC),
        results={},
        previous=None,
        n_sims=200,
    )

    assert state.fixtures[0].forecast is None
    assert state.fixtures[0].message == "live score is not available yet"
