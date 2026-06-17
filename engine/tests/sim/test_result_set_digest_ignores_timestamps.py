from __future__ import annotations

from wolves.sim.result_set import result_set_from_entries
from wolves.snapshot import ResultSetEntry


def test_result_set_digest_ignores_fetch_timestamps() -> None:
    first = result_set_from_entries(
        [
            ResultSetEntry(
                match=1,
                home_goals=2,
                away_goals=0,
                fetched_at="2026-06-16T12:00:00+00:00",
            )
        ]
    )
    second = result_set_from_entries(
        [
            ResultSetEntry(
                match=1,
                home_goals=2,
                away_goals=0,
                fetched_at="2026-06-16T13:00:00+00:00",
            )
        ]
    )
    changed = result_set_from_entries([ResultSetEntry(match=1, home_goals=2, away_goals=1)])

    assert first.digest == second.digest
    assert first.digest != changed.digest
