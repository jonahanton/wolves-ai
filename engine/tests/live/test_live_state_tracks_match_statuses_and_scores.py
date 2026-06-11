from __future__ import annotations

from datetime import UTC, datetime

from wolves.clients.api_football import FakeFixturesClient, MatchFixture
from wolves.config import Settings
from wolves.live import build_fixtures_client, live_pass, publishable_results
from wolves.live_state import LiveState, LiveStateStore, build_live_state
from wolves.models.contracts import ScorelineDistribution
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.format import load_format
from wolves.snapshot import MatchProbs, RunMeta, Snapshot


def _fixture(
    home: str = "Mexico",
    away: str = "South Africa",
    *,
    fixture_id: int = 1300001,
    day: str = "2026-06-11T19:00:00+00:00",
    status: str = "live",
    goals: tuple[int | None, int | None] = (0, 0),
    elapsed: int | None = 60,
) -> MatchFixture:
    return MatchFixture(
        fixture_id=fixture_id,
        kickoff=datetime.fromisoformat(day),
        status=status,
        home=home,
        away=away,
        home_goals=goals[0],
        away_goals=goals[1],
        elapsed=elapsed,
        city="Mexico City",
    )


class FakeLiveForecaster:
    def __init__(self) -> None:
        self.fmt = load_format(Settings().data_dir)
        self.fit_results_count: int | None = None

    def fit(self, *, extra_results=None):
        self.fit_results_count = len(extra_results or [])
        return None

    def match_probs(self, home: str, away: str, *, neutral: bool = True, match: int | None = None):
        return {"home": 0.45, "draw": 0.28, "away": 0.27}

    def score_grid(self, home: str, away: str, *, neutral: bool = True, match: int | None = None):
        return ScorelineDistribution.single(1, 1)

    def live_match(self, home: str, away: str, state, *, knockout: bool):
        if state.home_goals > state.away_goals:
            return {"home": 0.78, "draw": 0.15, "away": 0.07}
        return {"home": 0.40, "draw": 0.31, "away": 0.29}

    def live_distribution(self, home: str, away: str, state):
        return ScorelineDistribution.single(state.home_goals, state.away_goals)

    def title_probs(self, *, n_sims: int, seed: int = 0, results=None, live_distributions=None):
        dist = (live_distributions or {})[1]
        return {"mexico": 0.18 + 0.04 * dist.p_home, "south_africa": 0.06 + 0.03 * dist.p_away}


def test_score_changes_move_in_match_forecast_and_title_probs() -> None:
    forecaster = FakeLiveForecaster()
    fetched_at = datetime(2026, 6, 11, 19, 30, tzinfo=UTC)

    level = build_live_state(
        forecaster,
        [_fixture(goals=(0, 0))],
        fetched_at=fetched_at,
        results={},
        previous=None,
        n_sims=200,
    )
    leading = build_live_state(
        forecaster,
        [_fixture(goals=(1, 0))],
        fetched_at=fetched_at,
        results={},
        previous=None,
        n_sims=200,
    )

    assert level.fixtures[0].forecast is not None
    assert leading.fixtures[0].forecast is not None
    assert leading.fixtures[0].forecast.p_home > level.fixtures[0].forecast.p_home
    assert leading.title_probs["mexico"] > level.title_probs["mexico"]


def test_persisted_result_remains_publishable_until_latest_snapshot_contains_it() -> None:
    previous = Snapshot(
        run=RunMeta(
            run_id="run-20260611",
            created_at="2026-06-11T10:00:00+00:00",
            n_sims=10,
            engine_version="x",
            kind="sim_only",
        ),
        focus={"team_id": "england", "group": "L", "finish_probs": {}, "reach_probs": {}, "paths": []},
        slots=[],
        teams=[],
        matches=[
            MatchProbs(
                match=1,
                stage="group",
                date="2026-06-11",
                city="Mexico City",
                home_id="mexico",
                away_id="south_africa",
                p_home=0.5,
                p_draw=0.3,
                p_away=0.2,
            )
        ],
    )
    result = _result(1, 2, 0)

    pending = publishable_results({1: result}, file_results={1: result}, previous=previous)

    assert pending == {1: result}


def test_live_state_covers_scheduled_finished_abandoned_no_data_and_concurrent_games() -> None:
    forecaster = FakeLiveForecaster()
    fetched_at = datetime(2026, 6, 11, 19, 30, tzinfo=UTC)
    fixtures = [
        _fixture(status="scheduled", goals=(None, None), elapsed=None),
        _fixture(status="finished", goals=(2, 0), elapsed=90),
        _fixture("Czechia", "South Africa", fixture_id=1300030, status="abandoned", goals=(None, None), elapsed=None),
        _fixture("South Korea", "Czechia", fixture_id=1300002, status="live", goals=(1, 1), elapsed=55),
        _fixture("Mexico", "South Africa", fixture_id=1300003, status="live", goals=(1, 0), elapsed=70),
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
    fixture = _fixture(
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
        [_fixture(goals=(0, 0), elapsed=None)],
        fetched_at=datetime(2026, 6, 11, 19, 30, tzinfo=UTC),
        results={},
        previous=None,
        n_sims=200,
    )

    assert state.fixtures[0].forecast is None
    assert state.fixtures[0].message == "live score is not available yet"


def test_cloud_live_polling_requires_the_real_api_key(tmp_path) -> None:
    settings = Settings(runs_root=tmp_path, storage_mode="both", bucket="test-bucket", api_football_key="")

    try:
        build_fixtures_client(settings)
    except RuntimeError as exc:
        assert "API_FOOTBALL_KEY" in str(exc)
    else:
        raise AssertionError("missing API_FOOTBALL_KEY should fail for cloud-backed live polling")


def test_failed_poll_keeps_previous_live_state(tmp_path) -> None:
    store = LiveStateStore(ArtifactStore(Settings(runs_root=tmp_path, storage_mode="local")))
    state = LiveState(
        generated_at="2026-06-11T19:30:00+00:00",
        fetched_at="2026-06-11T19:30:00+00:00",
        stale_after="2026-06-11T19:32:00+00:00",
        live_match_count=1,
        fixtures=[_fixture_state()],
        title_probs={"mexico": 0.2},
    )
    store.put(state)

    failed = store.record_failure(message="timeout", now=datetime(2026, 6, 11, 19, 33, tzinfo=UTC))

    assert failed.poll_status == "failed"
    assert failed.fixtures == state.fixtures
    assert failed.message == "timeout"


async def test_live_pass_persists_state_even_before_full_time_results(tmp_path) -> None:
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    forecaster = FakeLiveForecaster()

    published = await live_pass(
        settings,
        fixtures=FakeFixturesClient([_fixture(goals=(1, 0), elapsed=68)]),
        n_sims=200,
        forecaster=forecaster,
    )

    state = LiveStateStore(ArtifactStore(settings)).load()
    assert published is False
    assert state is not None
    assert state.live_match_count == 1
    assert state.fixtures[0].forecast.source == "in_match"


def _fixture_state():
    return {
        "external_id": 1300001,
        "match": 1,
        "status": "live",
        "kickoff": "2026-06-11T19:00:00+00:00",
        "minute": 60,
        "home_id": "mexico",
        "away_id": "south_africa",
        "home_name": "Mexico",
        "away_name": "South Africa",
        "home_goals": 1,
        "away_goals": 0,
        "forecast": {"source": "in_match", "p_home": 0.78, "p_draw": 0.15, "p_away": 0.07},
    }


def _result(match: int, home_goals: int, away_goals: int):
    from wolves.sim.format import PlayedResult

    return PlayedResult(match=match, home_goals=home_goals, away_goals=away_goals)
