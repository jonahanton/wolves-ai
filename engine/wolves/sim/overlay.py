"""Map polled API-Football fixtures onto the sim's played-results overlay."""

from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING

from wolves.clients.odds.team_names import team_id_for_name
from wolves.sim.format import FormatData, GroupMatch, KnockoutMatch, PlayedResult

if TYPE_CHECKING:
    from wolves.clients.api_football import MatchFixture

logger = logging.getLogger(__name__)


def results_from_fixtures(fmt: FormatData, fixtures: list[MatchFixture]) -> dict[int, PlayedResult]:
    """Convert finished fixtures into the results overlay keyed by match number.

    In-play fixtures are deliberately excluded: a half-time score is not a
    result, and overlaying it would freeze the match at that score."""
    results: dict[int, PlayedResult] = {}
    for fixture in fixtures:
        if fixture.status != "finished" or fixture.home_goals is None or fixture.away_goals is None:
            continue
        resolved = _resolve(fmt, fixture)
        if resolved is None:
            logger.warning(
                "could not map finished fixture %s v %s on %s to a match",
                fixture.home,
                fixture.away,
                fixture.kickoff.date(),
            )
            continue
        results[resolved.match] = resolved
    return results


def _resolve(fmt: FormatData, fixture: MatchFixture) -> PlayedResult | None:
    home_id = team_id_for_name(fixture.home, fmt.teams)
    away_id = team_id_for_name(fixture.away, fmt.teams)
    if home_id is None or away_id is None:
        return None
    assert fixture.home_goals is not None and fixture.away_goals is not None

    group = _group_match(fmt, home_id, away_id)
    if group is not None:
        oriented = group.home == home_id
        return PlayedResult(
            match=group.match,
            home_goals=fixture.home_goals if oriented else fixture.away_goals,
            away_goals=fixture.away_goals if oriented else fixture.home_goals,
        )

    knockout = _knockout_match(fmt, fixture)
    if knockout is None:
        return None
    winner = _knockout_winner(fixture, home_id=home_id, away_id=away_id)
    if winner is None:
        logger.warning("finished knockout fixture %s v %s has no winner; skipping", fixture.home, fixture.away)
        return None
    return PlayedResult(
        match=knockout.match,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        winner=winner,
    )


def _group_match(fmt: FormatData, home_id: str, away_id: str) -> GroupMatch | None:
    by_pair = {(m.home, m.away): m for m in fmt.group_matches}
    return by_pair.get((home_id, away_id)) or by_pair.get((away_id, home_id))


def _knockout_match(fmt: FormatData, fixture: MatchFixture) -> KnockoutMatch | None:
    kickoff_date = fixture.kickoff.astimezone(UTC).date().isoformat()
    candidates = [m for m in fmt.knockout if m.date[:10] == kickoff_date]
    if len(candidates) == 1:
        return candidates[0]
    if fixture.city:
        city = fixture.city.casefold()
        narrowed = [m for m in candidates if city in m.city.casefold() or m.city.casefold() in city]
        if len(narrowed) == 1:
            return narrowed[0]
    return None


def _knockout_winner(fixture: MatchFixture, *, home_id: str, away_id: str) -> str | None:
    assert fixture.home_goals is not None and fixture.away_goals is not None
    if fixture.home_goals != fixture.away_goals:
        return home_id if fixture.home_goals > fixture.away_goals else away_id
    if fixture.winner == "home":
        return home_id
    if fixture.winner == "away":
        return away_id
    return None
