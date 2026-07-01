"""Run-local dataset overlay: append freshly completed results so a refit
sees them immediately, without waiting for the upstream backbone. The source
dataset is never mutated; the overlay is a per-run copy."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import duckdb

from wolves.data.contracts import MatchRecord
from wolves.models.contracts import DatasetHandle

_DATE_TOLERANCE_DAYS = 1


def _existing_pairs(connection: duckdb.DuckDBPyConnection, teams: set[str]) -> dict[frozenset[str], list[date]]:
    if not teams:
        return {}
    placeholders = ", ".join("?" for _ in teams)
    rows = connection.execute(
        f"select date, home_team, away_team from matches "
        f"where home_team in ({placeholders}) or away_team in ({placeholders})",
        [*teams, *teams],
    ).fetchall()
    index: dict[frozenset[str], list[date]] = {}
    for day, home, away in rows:
        index.setdefault(frozenset({home, away}), []).append(day)
    return index


def _novel_records(connection: duckdb.DuckDBPyConnection, records: list[MatchRecord]) -> list[MatchRecord]:
    """Drop records whose team pair already sits in the backbone within a day.

    The backbone keys teams and dates from the source feed while the overlay
    keys from the 2026 registry and UTC kickoff, so a match ingested upstream
    reappears here under a swapped orientation or a one-day-off date; matching
    the unordered pair inside a tolerance stops a refit double-counting it."""
    teams = {team for record in records for team in (record.home_team, record.away_team)}
    existing = _existing_pairs(connection, teams)

    def present(record: MatchRecord) -> bool:
        pair = frozenset({record.home_team, record.away_team})
        return any(abs((day - record.date).days) <= _DATE_TOLERANCE_DAYS for day in existing.get(pair, ()))

    return [record for record in records if not present(record)]


def overlay_results(dataset: DatasetHandle, records: list[MatchRecord], *, dest_dir: Path) -> DatasetHandle:
    """Copy the dataset and insert the records not already in the backbone."""
    if not records:
        return dataset
    source = duckdb.connect(str(dataset.path), read_only=True)
    try:
        novel = _novel_records(source, records)
    finally:
        source.close()
    if not novel:
        return dataset
    dest_dir.mkdir(parents=True, exist_ok=True)
    version = f"{dataset.dataset_id}+{len(novel)}r"
    dest = dest_dir / f"wolves-data-{version}.duckdb"
    shutil.copyfile(dataset.path, dest)
    connection = duckdb.connect(str(dest))
    try:
        connection.executemany(
            "insert into matches values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                [
                    r.date.isoformat(),
                    r.home_team,
                    r.away_team,
                    r.home_goals,
                    r.away_goals,
                    r.tournament,
                    r.importance,
                    r.neutral,
                ]
                for r in novel
            ],
        )
    finally:
        connection.close()
    return DatasetHandle(path=dest, dataset_id=version)
