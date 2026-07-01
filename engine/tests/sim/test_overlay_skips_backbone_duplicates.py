"""A mid-tournament refit must not double-count a result the backbone already
carries once upstream ingests it, even under a swapped home/away orientation or
a one-day UTC/local date drift."""

from __future__ import annotations

from datetime import date

from wolves.data.contracts import MatchRecord
from wolves.data.overlay import overlay_results
from wolves.data.query import DatasetQuery


def _record(home: str, away: str, *, day: date) -> MatchRecord:
    return MatchRecord(
        date=day,
        home_team=home,
        away_team=away,
        home_goals=1,
        away_goals=0,
        tournament="FIFA World Cup",
        importance=4.0,
        neutral=True,
    )


def test_overlay_drops_a_backbone_match_under_swapped_orientation_and_off_by_one_date(
    fixture_dataset, tmp_path
) -> None:
    duplicate = _record("beta", "alpha", day=date(2025, 3, 2))
    novel = _record("alpha", "beta", day=date(2026, 6, 20))

    overlaid = overlay_results(fixture_dataset, [duplicate, novel], dest_dir=tmp_path)

    with DatasetQuery(overlaid) as fresh, DatasetQuery(fixture_dataset) as source:
        assert (
            fresh.sql("select count(*) n from matches")[0]["n"]
            == source.sql("select count(*) n from matches")[0]["n"] + 1
        )
        assert fresh.sql("select count(*) n from matches where date = '2026-06-20'")[0]["n"] == 1
        assert fresh.sql("select count(*) n from matches where date = '2025-03-02'")[0]["n"] == 0


def test_overlay_returns_the_source_when_every_record_is_a_duplicate(fixture_dataset, tmp_path) -> None:
    duplicate = _record("beta", "alpha", day=date(2025, 3, 1))

    overlaid = overlay_results(fixture_dataset, [duplicate], dest_dir=tmp_path)

    assert overlaid.dataset_id == fixture_dataset.dataset_id
