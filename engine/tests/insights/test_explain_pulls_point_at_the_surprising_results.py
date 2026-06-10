from __future__ import annotations

from datetime import date

from wolves.config import Settings
from wolves.data.contracts import MatchRecord
from wolves.data.overlay import overlay_results
from wolves.forecast import Forecaster
from wolves.insights.explain import model_explain


def test_an_upset_thrashing_is_the_strongest_upward_pull(fixture_dataset, tmp_path) -> None:
    upsets = [
        MatchRecord(
            date=date(2026, 1, 20),
            home_team="delta",
            away_team="alpha",
            home_goals=5,
            away_goals=0,
            tournament="Friendly",
            importance=1.0,
            neutral=True,
        )
    ]
    overlaid = overlay_results(fixture_dataset, upsets, dest_dir=tmp_path)
    forecaster = Forecaster(Settings(runs_root=tmp_path, storage_mode="local"), dataset=overlaid)
    forecaster.fit(as_of=date(2026, 2, 1))

    explanation = model_explain(forecaster, "delta")

    top = explanation.strongest_pulls_up[0]
    assert top.opponent == "alpha"
    assert top.score == "5-0"
    assert top.pull > 0
    assert explanation.model_rank >= 1
    assert sum(i.pull_share for i in explanation.strongest_pulls_up + explanation.strongest_pulls_down) <= 1.0 + 1e-6
    assert explanation.weighted_record.matches > 0
