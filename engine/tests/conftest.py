from __future__ import annotations

from datetime import date as _date
from typing import Any

import pandas as pd
import pytest

from wolves.agent.contracts import ForecastSubmission, Narrative, RatingOverride
from wolves.data.build import write_dataset
from wolves.models.contracts import DatasetHandle


@pytest.fixture(autouse=True)
def _fake_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin fake credentials so moto-backed tests never sign with, or fall
    through to, a real AWS profile on the developer machine."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


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
        "rating_overrides": [
            RatingOverride(
                team_id="england",
                delta_elo=15.0,
                cause="First-choice keeper confirmed fit",
                ledger_ids=["led-0001"],
            )
        ],
        "england_reach_probs": {
            "r32": 0.97,
            "r16": 0.62,
            "qf": 0.38,
            "sf": 0.22,
            "final": 0.13,
            "champion": 0.07,
        },
        "narrative": build_narrative(),
        "delta_vs_market": 0.01,
        "delta_vs_yesterday": 0.0,
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
    out_dir = tmp_path_factory.mktemp("dataset")
    write_dataset(out_dir, version="test", tables={"matches": pd.DataFrame(_round_robin_rows())}, hashes={})
    return DatasetHandle(path=out_dir / "wolves-data-test.duckdb", version="test")
