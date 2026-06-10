from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from wolves.data.build import write_dataset
from wolves.models.contracts import DatasetHandle

TEAMS = ["alpha", "beta", "gamma", "delta"]


def _round_robin_rows() -> list[dict]:
    """Eight seasons of round robins where alpha > beta > gamma > delta."""
    goals = {"alpha": 3, "beta": 2, "gamma": 1, "delta": 0}
    rows = []
    for year in range(2018, 2026):
        for i, home in enumerate(TEAMS):
            for away in TEAMS[i + 1 :]:
                rows.append(
                    {
                        "date": date(year, 3, 1),
                        "home_team": home,
                        "away_team": away,
                        "home_goals": goals[home] + 1,
                        "away_goals": goals[away],
                        "tournament": "Friendly",
                        "importance": 1.0,
                        "neutral": False,
                    }
                )
    return rows * 11


@pytest.fixture(scope="session")
def fixture_dataset(tmp_path_factory) -> DatasetHandle:
    out_dir = tmp_path_factory.mktemp("dataset")
    write_dataset(out_dir, version="test", tables={"matches": pd.DataFrame(_round_robin_rows())}, hashes={})
    return DatasetHandle(path=out_dir / "wolves-data-test.duckdb", version="test")
