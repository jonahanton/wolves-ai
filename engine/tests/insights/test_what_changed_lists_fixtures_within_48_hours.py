from __future__ import annotations

from datetime import date

from wolves.insights.what_changed import fixtures_within
from wolves.sim.format import FormatData, GroupMatch, KnockoutMatch


def _group(match: int, when: str, home: str, away: str) -> GroupMatch:
    return GroupMatch(match=match, group="A", date=when, city="Dallas", home=home, away=away)


FMT = FormatData(
    teams=[],
    group_matches=[
        _group(1, "2026-06-10T19:00:00Z", "mexico", "south-africa"),
        _group(2, "2026-06-11T19:00:00Z", "england", "croatia"),
        _group(3, "2026-06-12T20:00:00Z", "france", "senegal"),
        _group(4, "2026-06-13T01:00:00Z", "spain", "chile"),
    ],
    knockout=[KnockoutMatch(match=73, stage="r32", date="2026-06-12T18:00:00Z", city="Dallas", home="1A", away="2B")],
    venues=[],
)


def test_only_fixtures_in_next_48_hours_listed_in_kickoff_order() -> None:
    assert fixtures_within(FMT, on=date(2026, 6, 11)) == [
        "england vs croatia on 2026-06-11",
        "1A vs 2B on 2026-06-12",
        "france vs senegal on 2026-06-12",
    ]
