from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from wolves.agent.ledger import EvidenceLedger
from wolves.insights.what_changed import played_since, what_changed
from wolves.snapshot import FocusTeamBlock, RunMeta, Snapshot

ROWS = [
    ("2026-06-08", "England", "Croatia", 2, 0),
    ("2026-06-09", "France", "Senegal", 1, 1),
    ("2026-06-10", "Spain", "Chile", 3, 1),
    ("2026-06-11", "Brazil", "Ghana", 2, 2),
]


def _dataset(tmp_path: Path) -> Path:
    path = tmp_path / "dataset.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute(
        "create table matches (date date, home_team varchar, away_team varchar, home_goals int, away_goals int)"
    )
    connection.executemany("insert into matches values (?, ?, ?, ?, ?)", ROWS)
    connection.close()
    return path


def test_only_matches_in_window_returned_oldest_first(tmp_path: Path) -> None:
    played = played_since(_dataset(tmp_path), since=date(2026, 6, 9), until=date(2026, 6, 10))
    assert [(m.home_team, m.away_team) for m in played] == [("France", "Senegal"), ("Spain", "Chile")]
    assert played[0].summary() == "France 1-1 Senegal (2026-06-09)"


def test_digest_counts_and_lists_played_results(tmp_path: Path) -> None:
    played = played_since(_dataset(tmp_path), since=date(2026, 6, 9), until=date(2026, 6, 10))
    snapshot = Snapshot(
        run=RunMeta(
            run_id="agent-d1", created_at="2026-06-09T08:00:00+00:00", n_sims=1000, engine_version="x", kind="agent"
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={"champion": 0.07}, paths=[]),
        slots=[],
        teams=[],
    )
    diff = what_changed(
        previous=snapshot,
        current_titles=None,
        ledger=EvidenceLedger(tmp_path / "ledger.jsonl"),
        source_memory=None,
        run_id="agent-d2",
        as_of="2026-06-10",
        played_results=played,
    )
    assert "2 result(s) played since: France 1-1 Senegal (2026-06-09); Spain 3-1 Chile (2026-06-10)." in diff.digest()
