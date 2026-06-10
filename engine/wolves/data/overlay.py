"""Run-local dataset overlay: append freshly completed results so a refit
sees them immediately, without waiting for the upstream backbone. The source
dataset is never mutated; the overlay is a per-run copy."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from wolves.data.contracts import MatchRecord
from wolves.models.contracts import DatasetHandle


def overlay_results(dataset: DatasetHandle, records: list[MatchRecord], *, dest_dir: Path) -> DatasetHandle:
    """Copy the dataset and insert the records; returns the overlaid handle."""
    if not records:
        return dataset
    dest_dir.mkdir(parents=True, exist_ok=True)
    version = f"{dataset.version}+{len(records)}r"
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
                for r in records
            ],
        )
    finally:
        connection.close()
    return DatasetHandle(path=dest, version=version)
