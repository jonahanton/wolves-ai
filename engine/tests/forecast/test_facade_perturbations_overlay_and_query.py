from __future__ import annotations

from datetime import date

from wolves.data.contracts import MatchRecord
from wolves.data.overlay import overlay_results
from wolves.data.query import DatasetQuery
from wolves.models.poisson import PoissonDecayModel


def _record(home: str, away: str, hg: int, ag: int) -> MatchRecord:
    return MatchRecord(
        date=date(2026, 1, 15),
        home_team=home,
        away_team=away,
        home_goals=hg,
        away_goals=ag,
        tournament="Friendly",
        importance=1.0,
        neutral=True,
    )


def test_overlay_appends_results_without_mutating_the_source(fixture_dataset, tmp_path) -> None:
    overlaid = overlay_results(fixture_dataset, [_record("alpha", "beta", 9, 0)], dest_dir=tmp_path)

    with DatasetQuery(overlaid) as fresh, DatasetQuery(fixture_dataset) as source:
        assert (
            fresh.sql("select count(*) n from matches")[0]["n"]
            == source.sql("select count(*) n from matches")[0]["n"] + 1
        )
    assert overlaid.dataset_id != fixture_dataset.dataset_id


def test_overlaid_results_move_the_refit(fixture_dataset, tmp_path) -> None:
    model = PoissonDecayModel()
    base = model.fit(fixture_dataset, as_of=date(2026, 2, 1))
    thrashings = [_record("delta", "alpha", 5, 0) for _ in range(8)]
    overlaid = overlay_results(fixture_dataset, thrashings, dest_dir=tmp_path)
    refit = model.fit(overlaid, as_of=date(2026, 2, 1))

    assert refit.strength_of("delta") > base.strength_of("delta")
    assert refit.strength_of("alpha") < base.strength_of("alpha")


def test_query_surface_is_read_only(fixture_dataset) -> None:
    import duckdb
    import pytest

    with DatasetQuery(fixture_dataset) as query:
        rows = query.team_form("alpha", last=3)
        assert len(rows) == 3
        with pytest.raises(duckdb.Error):
            query.sql("drop table matches")
