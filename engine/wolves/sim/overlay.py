"""Map polled API-Football fixtures onto the sim's played-results overlay."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from wolves.clients.odds.team_names import team_id_for_name
from wolves.sim.format import FormatData, GroupMatch, KnockoutMatch, PlayedResult

if TYPE_CHECKING:
    from wolves.clients.api_football import GoalEvent, MatchFixture

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FixtureResolution:
    match: int
    home_id: str
    away_id: str
    home_goals: int | None
    away_goals: int | None
    home_reds: int
    away_reds: int
    knockout: bool
    reg_home_goals: int | None = None
    reg_away_goals: int | None = None
    goals: tuple[GoalEvent, ...] = ()
    home_shots_on: int | None = None
    away_shots_on: int | None = None
    home_total_shots: int | None = None
    away_total_shots: int | None = None
    home_possession: float | None = None
    away_possession: float | None = None


def results_from_fixtures(fmt: FormatData, fixtures: list[MatchFixture]) -> dict[int, PlayedResult]:
    """Convert finished fixtures into the played-results overlay."""
    results: dict[int, PlayedResult] = {}
    for fixture in fixtures:
        if fixture.status != "finished" or fixture.home_goals is None or fixture.away_goals is None:
            continue
        resolved = resolve_fixture(fmt, fixture)
        if resolved is None:
            logger.warning(
                "could not map finished fixture %s v %s on %s to a match",
                fixture.home,
                fixture.away,
                fixture.kickoff.date(),
            )
            continue
        winner = _winner_from_fixture(fixture, home_id=resolved.home_id, away_id=resolved.away_id)
        if resolved.knockout and winner is None:
            logger.warning("finished knockout fixture %s v %s has no winner; skipping", fixture.home, fixture.away)
            continue
        results[resolved.match] = PlayedResult(
            match=resolved.match,
            home_goals=resolved.home_goals,
            away_goals=resolved.away_goals,
            winner=winner if resolved.knockout else None,
        )
    return results


def resolve_fixture(fmt: FormatData, fixture: MatchFixture) -> FixtureResolution | None:
    """Map a provider fixture onto the tournament match id and schedule orientation."""
    home_id = team_id_for_name(fixture.home, fmt.teams)
    away_id = team_id_for_name(fixture.away, fmt.teams)
    if home_id is None or away_id is None:
        return None

    group = _group_match(fmt, home_id, away_id)
    if group is not None:
        oriented = group.home == home_id
        return FixtureResolution(
            match=group.match,
            home_id=group.home,
            away_id=group.away,
            home_goals=fixture.home_goals if oriented else fixture.away_goals,
            away_goals=fixture.away_goals if oriented else fixture.home_goals,
            reg_home_goals=fixture.fulltime_home if oriented else fixture.fulltime_away,
            reg_away_goals=fixture.fulltime_away if oriented else fixture.fulltime_home,
            home_reds=fixture.home_reds if oriented else fixture.away_reds,
            away_reds=fixture.away_reds if oriented else fixture.home_reds,
            knockout=False,
            goals=_oriented_goals(fixture, flip=not oriented),
            **_oriented_stats(fixture, flip=not oriented),
        )

    knockout = _knockout_match(fmt, fixture)
    if knockout is None:
        return None
    return FixtureResolution(
        match=knockout.match,
        home_id=home_id,
        away_id=away_id,
        home_goals=fixture.home_goals,
        away_goals=fixture.away_goals,
        reg_home_goals=fixture.fulltime_home,
        reg_away_goals=fixture.fulltime_away,
        home_reds=fixture.home_reds,
        away_reds=fixture.away_reds,
        knockout=True,
        goals=_oriented_goals(fixture, flip=False),
        **_oriented_stats(fixture, flip=False),
    )


def _oriented_goals(fixture: MatchFixture, *, flip: bool) -> tuple[GoalEvent, ...]:
    if not flip:
        return tuple(fixture.goals)
    from wolves.clients.api_football import GoalEvent

    return tuple(GoalEvent(minute=g.minute, side="away" if g.side == "home" else "home") for g in fixture.goals)


def _oriented_stats(fixture: MatchFixture, *, flip: bool) -> dict[str, int | float | None]:
    home, away = ("away", "home") if flip else ("home", "away")
    return {
        "home_shots_on": getattr(fixture, f"{home}_shots_on"),
        "away_shots_on": getattr(fixture, f"{away}_shots_on"),
        "home_total_shots": getattr(fixture, f"{home}_total_shots"),
        "away_total_shots": getattr(fixture, f"{away}_total_shots"),
        "home_possession": getattr(fixture, f"{home}_possession"),
        "away_possession": getattr(fixture, f"{away}_possession"),
    }


def _group_match(fmt: FormatData, home_id: str, away_id: str) -> GroupMatch | None:
    by_pair = {(m.home, m.away): m for m in fmt.group_matches}
    return by_pair.get((home_id, away_id)) or by_pair.get((away_id, home_id))


# Schedule host regions vs provider stadium municipalities; used only by the rescheduled-kickoff fallback.
_PROVIDER_CITY_ALIASES = {
    "east rutherford": "new york/new jersey",
    "new jersey": "new york/new jersey",
    "new york": "new york/new jersey",
    "santa clara": "san francisco bay area",
    "san francisco": "san francisco bay area",
    "inglewood": "los angeles",
    "arlington": "dallas",
    "foxborough": "boston",
    "foxboro": "boston",
    "guadalupe": "monterrey",
    "miami gardens": "miami",
    "zapopan": "guadalajara",
}


def _knockout_match(fmt: FormatData, fixture: MatchFixture) -> KnockoutMatch | None:
    kickoff = fixture.kickoff.astimezone(UTC)
    exact = [m for m in fmt.knockout if datetime.fromisoformat(m.date) == kickoff]
    if len(exact) == 1:
        return exact[0]
    candidates = [m for m in fmt.knockout if m.date[:10] == kickoff.date().isoformat()]
    if len(candidates) == 1:
        return candidates[0]
    if fixture.city:
        city = fixture.city.casefold()
        city = _PROVIDER_CITY_ALIASES.get(city, city)
        narrowed = [m for m in candidates if city in m.city.casefold() or m.city.casefold() in city]
        if len(narrowed) == 1:
            return narrowed[0]
    return None


def _winner_from_fixture(fixture: MatchFixture, *, home_id: str, away_id: str) -> str | None:
    if fixture.home_goals is not None and fixture.away_goals is not None and fixture.home_goals != fixture.away_goals:
        return home_id if fixture.home_goals > fixture.away_goals else away_id
    if fixture.winner == "home":
        return home_id
    if fixture.winner == "away":
        return away_id
    return None
