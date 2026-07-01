"""A knockout decided in extra time or on penalties must enter the strength
refit at its 90-minute score; the model is a regulation goal model, and ET goals
would inflate the winner's fitted attack."""

from __future__ import annotations

from datetime import datetime

from wolves.clients.api_football import MatchFixture
from wolves.clients.api_football.client import _to_fixture
from wolves.config import Settings
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.results_store import ResultsStore, played_match_records


def test_to_fixture_parses_the_regulation_score_block() -> None:
    item = {
        "fixture": {"id": 5, "date": "2026-06-28T19:00:00+00:00", "status": {"short": "AET"}},
        "teams": {"home": {"name": "Mexico", "winner": True}, "away": {"name": "England", "winner": False}},
        "goals": {"home": 2, "away": 1},
        "score": {"fulltime": {"home": 1, "away": 1}, "extratime": {"home": 2, "away": 1}, "penalty": None},
    }

    fixture = _to_fixture(item)

    assert (fixture.home_goals, fixture.away_goals) == (2, 1)
    assert (fixture.fulltime_home, fixture.fulltime_away) == (1, 1)


def test_extra_time_knockout_refits_on_the_regulation_draw(tmp_path) -> None:
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    fixture = MatchFixture(
        fixture_id=73,
        kickoff=datetime.fromisoformat("2026-06-28T19:00:00+00:00"),
        status="finished",
        home="Mexico",
        away="England",
        home_goals=2,
        away_goals=1,
        fulltime_home=1,
        fulltime_away=1,
        city="Los Angeles",
        winner="home",
    )
    ResultsStore(ArtifactStore(settings)).record({}, fixtures=[fixture])

    records = {record.home_team: record for record in played_match_records(settings)}

    assert (records["mexico"].home_goals, records["mexico"].away_goals) == (1, 1)


def test_regulation_score_falls_back_to_the_aggregate_when_absent(tmp_path) -> None:
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    fixture = MatchFixture(
        fixture_id=73,
        kickoff=datetime.fromisoformat("2026-06-28T19:00:00+00:00"),
        status="finished",
        home="Mexico",
        away="England",
        home_goals=3,
        away_goals=0,
        city="Los Angeles",
        winner="home",
    )
    ResultsStore(ArtifactStore(settings)).record({}, fixtures=[fixture])

    records = {record.home_team: record for record in played_match_records(settings)}

    assert (records["mexico"].home_goals, records["mexico"].away_goals) == (3, 0)
