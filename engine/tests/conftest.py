from __future__ import annotations

from collections.abc import Iterator
from datetime import date as _date
from typing import Any

import pandas as pd
import pytest

from wolves.agent.contracts import ForecastSubmission, Narrative
from wolves.data.build import write_dataset
from wolves.models.contracts import DatasetHandle


# Session-scoped so the pin lands before any session fixture builds Settings;
# fake credentials keep moto-backed tests off the developer's real AWS profile.
@pytest.fixture(scope="session", autouse=True)
def _fake_aws_credentials() -> Iterator[None]:
    patch = pytest.MonkeyPatch()
    patch.setenv("AWS_ACCESS_KEY_ID", "testing")
    patch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    patch.setenv("AWS_SESSION_TOKEN", "testing")
    patch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    patch.delenv("AWS_PROFILE", raising=False)
    patch.setenv("STORAGE_MODE", "local")
    yield
    patch.undo()


R32_MATCHES = [str(m) for m in range(73, 89)]


def build_narrative(**overrides: Any) -> Narrative:
    fields: dict[str, Any] = {
        "england_story": "England are settled and the squad trained in full ahead of Croatia.",
        "slot_rationales": {m: f"Slot {m}: favourite advances on rating gap." for m in R32_MATCHES},
        "travel_memo": "Win the group and England stay east; second means a longer hop west.",
    }
    fields.update(overrides)
    return Narrative(**fields)


def build_submission(**overrides: Any) -> ForecastSubmission:
    fields: dict[str, Any] = {
        "artifact_id": "mixture-001",
        "narrative": build_narrative(),
        "evidence_ids": ["led-0001"],
    }
    fields.update(overrides)
    return ForecastSubmission(**fields)


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
                        "date": _date(year, 3, 1),
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
    from wolves.data.build import _frame
    from wolves.data.contracts import TeamRecord
    from wolves.data.sources.elo_history import EloHistoryRecord
    from wolves.data.sources.market_closes import ClosingOddsRecord, OutrightCloseRecord

    out_dir = tmp_path_factory.mktemp("dataset")
    write_dataset(
        out_dir,
        dataset_id="test",
        tables={
            "matches": pd.DataFrame(_round_robin_rows()),
            "teams": _frame([TeamRecord(team=t) for t in TEAMS], TeamRecord),
            "elo_history": _frame([], EloHistoryRecord),
            "market_closes": _frame([], ClosingOddsRecord),
            "outright_closes": _frame([], OutrightCloseRecord),
        },
        hashes={},
    )
    return DatasetHandle(path=out_dir / "wolves-data-test.duckdb", dataset_id="test")
