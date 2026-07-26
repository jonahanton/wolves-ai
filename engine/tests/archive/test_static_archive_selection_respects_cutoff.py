from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wolves.archive.selection import ArchiveSelectionError, archive_cutoff, normalise_results, select_snapshot
from wolves.archive.source import FixtureMetadata
from wolves.snapshot import Snapshot


def snapshot(*, run_id: str, created_at: str, kind: str = "agent", result_recorded_at: str | None = None) -> Snapshot:
    return Snapshot.model_validate(
        {
            "run": {
                "run_id": run_id,
                "created_at": created_at,
                "as_of": created_at[:10],
                "n_sims": 1,
                "engine_version": "test",
                "kind": kind,
            },
            "focus": {"team_id": "england", "group": "A", "finish_probs": {}, "reach_probs": {}, "paths": []},
            "slots": [
                {
                    "match": 1,
                    "stage": "group",
                    "date": "2026-06-10T19:00:00Z",
                    "city": "New York",
                    "home": {"label": "A1", "candidates": []},
                    "away": {"label": "A2", "candidates": []},
                }
            ],
            "teams": [{"team_id": "england", "name": "England", "group": "A", "elo": 1800}],
            "result_set": {
                "results": [
                    {
                        "match": 1,
                        "home_id": "england",
                        "away_id": "france",
                        "home_goals": 1,
                        "away_goals": 0,
                        "fetched_at": result_recorded_at,
                    }
                ]
                if result_recorded_at
                else []
            },
        }
    )


def test_selects_latest_complete_agent_snapshot_on_the_same_day():
    cutoff = archive_cutoff("2026-06-10")

    selected = select_snapshot(
        [
            snapshot(run_id="agent-early", created_at="2026-06-10T10:00:00Z"),
            snapshot(run_id="agent-late", created_at="2026-06-10T20:00:00Z"),
        ],
        cutoff=cutoff,
    )

    assert selected.run.run_id == "agent-late"


def test_uses_complete_non_agent_snapshot_only_when_no_agent_exists():
    cutoff = archive_cutoff("2026-06-10")

    selected = select_snapshot(
        [snapshot(run_id="live-late", created_at="2026-06-10T20:00:00Z", kind="live")], cutoff=cutoff
    )

    assert selected.run.run_id == "live-late"


def test_new_york_cutoff_includes_before_midnight_and_excludes_after_midnight():
    cutoff = archive_cutoff("2026-06-10")

    selected = select_snapshot(
        [
            snapshot(run_id="agent-before", created_at="2026-06-11T03:59:58Z"),
            snapshot(run_id="agent-after", created_at="2026-06-11T04:00:00Z"),
        ],
        cutoff=cutoff,
    )

    assert cutoff == datetime(2026, 6, 11, 3, 59, 59, 999999, tzinfo=UTC)
    assert selected.run.run_id == "agent-before"


def test_result_normaliser_omits_results_recorded_after_the_cutoff():
    cutoff = archive_cutoff("2026-06-10")
    selected = snapshot(
        run_id="agent-future-result",
        created_at="2026-06-10T20:00:00Z",
        result_recorded_at="2026-06-11T04:00:00Z",
    )

    assert normalise_results(selected, cutoff=cutoff) == []


def test_result_normaliser_rejects_results_without_selected_snapshot_fixture_metadata():
    selected = snapshot(
        run_id="agent-missing",
        created_at="2026-06-10T20:00:00Z",
        result_recorded_at="2026-06-10T20:00:00Z",
    )
    selected.slots.clear()

    with pytest.raises(ArchiveSelectionError, match="no fixture or slot"):
        normalise_results(selected, cutoff=archive_cutoff("2026-06-10"))


def test_result_normaliser_uses_published_fixture_metadata_when_snapshot_omits_a_settled_match():
    selected = snapshot(
        run_id="agent-settled",
        created_at="2026-06-10T20:00:00Z",
        result_recorded_at="2026-06-10T20:00:00Z",
    )
    selected.slots.clear()

    results = normalise_results(
        selected,
        cutoff=archive_cutoff("2026-06-10"),
        fixture_metadata={1: FixtureMetadata(date="2026-06-10T19:00:00Z", stage="group")},
    )

    assert results[0].date == "2026-06-10T19:00:00Z"


def test_legacy_narrative_fields_survive_archive_validation():
    base = snapshot(run_id="agent-legacy", created_at="2026-06-10T20:00:00Z")
    selected = Snapshot.model_validate(
        {
            **base.model_dump(mode="json"),
            "agent": {
                "narrative": {
                    "focus_story": "Legacy focus",
                    "slot_rationales": {"R32-A": "Legacy rationale"},
                    "travel_memo": "Legacy travel",
                }
            },
        }
    )

    round_trip = selected.model_dump(mode="json")["agent"]["narrative"]

    assert round_trip["focus_story"] == "Legacy focus"
    assert round_trip["slot_rationales"] == {"R32-A": "Legacy rationale"}
    assert round_trip["travel_memo"] == "Legacy travel"
