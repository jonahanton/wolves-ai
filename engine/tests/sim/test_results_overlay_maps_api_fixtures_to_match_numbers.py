from __future__ import annotations

from datetime import datetime

import pytest

from wolves.clients.api_football import GoalEvent, MatchFixture
from wolves.config import Settings
from wolves.sim.format import load_format
from wolves.sim.overlay import resolve_fixture, results_from_fixtures


@pytest.fixture(scope="module")
def fmt():
    return load_format(Settings().data_dir)


def _fixture(**overrides) -> MatchFixture:
    fields = {
        "fixture_id": 1,
        "kickoff": datetime.fromisoformat("2026-06-11T13:00:00-06:00"),
        "status": "finished",
        "home": "Mexico",
        "away": "South Africa",
        "home_goals": 2,
        "away_goals": 0,
    }
    fields.update(overrides)
    return MatchFixture(**fields)


def test_finished_group_fixture_maps_to_its_match_number(fmt):
    results = results_from_fixtures(fmt, [_fixture()])

    assert set(results) == {1}
    assert (results[1].home_goals, results[1].away_goals) == (2, 0)


def test_reversed_feed_orientation_and_aliases_swap_goals_to_schedule_order(fmt):
    fixture = _fixture(home="Czechia", away="South Korea", home_goals=1, away_goals=3)

    results = results_from_fixtures(fmt, [fixture])

    assert set(results) == {2}
    assert (results[2].home_goals, results[2].away_goals) == (3, 1)


def test_reversed_orientation_flips_goal_event_sides(fmt):
    fixture = _fixture(
        home="Czechia",
        away="South Korea",
        home_goals=1,
        away_goals=3,
        goals=[GoalEvent(minute=10, side="home"), GoalEvent(minute=40, side="away")],
    )

    resolved = resolve_fixture(fmt, fixture)

    assert resolved is not None
    assert [(g.minute, g.side) for g in resolved.goals] == [(10, "away"), (40, "home")]


def test_provider_ampersand_team_names_resolve(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-12T15:00:00-04:00"),
        home="Canada",
        away="Bosnia & Herzegovina",
        home_goals=1,
        away_goals=0,
    )

    assert set(results_from_fixtures(fmt, [fixture])) == {3}


def test_in_play_and_scheduled_fixtures_are_excluded(fmt):
    fixtures = [
        _fixture(status="live", home_goals=1, away_goals=0),
        _fixture(status="scheduled", home_goals=None, away_goals=None),
    ]

    assert results_from_fixtures(fmt, fixtures) == {}


def test_knockout_on_a_unique_date_maps_without_a_city(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-28T12:00:00-07:00"),
        home="England",
        away="France",
        home_goals=2,
        away_goals=1,
        city=None,
    )

    results = results_from_fixtures(fmt, [fixture])

    assert set(results) == {73}
    assert results[73].winner == "england"


def test_knockout_draw_uses_the_winner_flag_and_city_narrows_shared_dates(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-30T17:00:00-04:00"),
        home="England",
        away="France",
        home_goals=1,
        away_goals=1,
        city="New Jersey",
        winner="away",
    )

    results = results_from_fixtures(fmt, [fixture])

    assert set(results) == {77}
    assert results[77].winner == "france"


def test_knockout_draw_without_a_winner_flag_is_skipped(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-30T17:00:00-04:00"),
        home="England",
        away="France",
        home_goals=1,
        away_goals=1,
        city="New Jersey",
    )

    assert results_from_fixtures(fmt, [fixture]) == {}


def test_knockout_with_an_unrecognised_kickoff_and_no_city_is_skipped(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-30T17:30:00-04:00"),
        home="England",
        away="France",
        home_goals=2,
        away_goals=1,
        city=None,
    )

    assert results_from_fixtures(fmt, [fixture]) == {}


def test_knockout_resolves_by_exact_kickoff_despite_a_municipal_venue_city(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-30T17:00:00-04:00"),
        home="England",
        away="France",
        home_goals=2,
        away_goals=1,
        city="East Rutherford",
    )

    assert set(results_from_fixtures(fmt, [fixture])) == {77}


def test_rescheduled_knockout_kickoff_falls_back_to_the_city_alias(fmt):
    fixture = _fixture(
        kickoff=datetime.fromisoformat("2026-06-30T18:30:00-04:00"),
        home="England",
        away="France",
        home_goals=2,
        away_goals=1,
        city="East Rutherford",
    )

    assert set(results_from_fixtures(fmt, [fixture])) == {77}
