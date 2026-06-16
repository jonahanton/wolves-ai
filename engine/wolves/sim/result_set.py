from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence

from wolves.clients.api_football import MatchFixture
from wolves.sim.format import FormatData, PlayedResult
from wolves.sim.overlay import FixtureResolution, resolve_fixture
from wolves.snapshot import ResultSetBlock, ResultSetEntry


def build_result_set(
    fmt: FormatData,
    results: Mapping[int, PlayedResult],
    *,
    fixtures: Sequence[MatchFixture] = (),
    fetched_at: str = "",
    source_matches: Iterable[int] = (),
) -> ResultSetBlock:
    sourced = set(source_matches)
    resolved = _resolved_fixtures(fmt, fixtures)
    entries = [
        _entry(fmt, result, resolved.get(match), fetched_at=fetched_at if match in sourced else None)
        for match, result in sorted(results.items())
    ]
    return result_set_from_entries(entries)


def result_set_from_entries(entries: Iterable[ResultSetEntry]) -> ResultSetBlock:
    ordered = sorted(entries, key=lambda entry: entry.match)
    return ResultSetBlock(digest=result_set_digest(ordered), results=ordered)


def result_set_digest(entries: Iterable[ResultSetEntry]) -> str:
    payload = [
        {
            "match": entry.match,
            "home_goals": entry.home_goals,
            "away_goals": entry.away_goals,
            "winner": entry.winner,
        }
        for entry in sorted(entries, key=lambda item: item.match)
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolved_fixtures(
    fmt: FormatData,
    fixtures: Sequence[MatchFixture],
) -> dict[int, tuple[MatchFixture, FixtureResolution]]:
    out = {}
    for fixture in fixtures:
        resolution = resolve_fixture(fmt, fixture)
        if resolution is not None:
            out[resolution.match] = (fixture, resolution)
    return out


def _entry(
    fmt: FormatData,
    result: PlayedResult,
    resolved: tuple[MatchFixture, FixtureResolution] | None,
    *,
    fetched_at: str | None,
) -> ResultSetEntry:
    if resolved is not None:
        fixture, resolution = resolved
        return ResultSetEntry(
            match=result.match,
            home_id=resolution.home_id,
            away_id=resolution.away_id,
            home_goals=result.home_goals,
            away_goals=result.away_goals,
            winner=result.winner,
            source_fixture_id=fixture.fixture_id,
            fetched_at=fetched_at,
        )
    home_id, away_id = _scheduled_teams(fmt, result.match)
    return ResultSetEntry(
        match=result.match,
        home_id=home_id,
        away_id=away_id,
        home_goals=result.home_goals,
        away_goals=result.away_goals,
        winner=result.winner,
        fetched_at=fetched_at,
    )


def _scheduled_teams(fmt: FormatData, match: int) -> tuple[str | None, str | None]:
    group = next((fixture for fixture in fmt.group_matches if fixture.match == match), None)
    if group is not None:
        return group.home, group.away
    return None, None
