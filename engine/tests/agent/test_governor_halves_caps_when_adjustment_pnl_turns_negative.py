from __future__ import annotations

from pathlib import Path

import pytest

from wolves.agent.calibration import (
    CalibrationLedger,
    MatchForecast,
    MatchScore,
    governor_scale,
    score_match,
    summarise_scores,
)


def _forecast(*, adjusted: bool = True, model_home: float = 0.6) -> MatchForecast:
    return MatchForecast(
        match_id="m1",
        date="2026-06-17",
        home="england",
        away="croatia",
        model_probs={"home": model_home, "draw": 0.25, "away": 1.0 - model_home - 0.25},
        market_probs={"home": 0.55, "draw": 0.27, "away": 0.18},
        frozen_sim_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
        adjusted=adjusted,
    )


def test_scores_cover_all_baselines_and_pnl_is_log_loss_saved():
    score = score_match(_forecast(), "home")
    assert set(score.brier) == {"model", "uniform", "market", "frozen_sim"}
    assert score.brier["model"] < score.brier["uniform"]
    assert score.adjustment_pnl == pytest.approx(score.log_loss["frozen_sim"] - score.log_loss["model"])
    assert score.adjustment_pnl > 0


def test_unadjusted_matches_carry_no_pnl():
    assert score_match(_forecast(adjusted=False), "home").adjustment_pnl is None


def test_governor_halves_caps_only_on_negative_trailing_pnl():
    good = score_match(_forecast(model_home=0.7), "home")
    bad = score_match(_forecast(model_home=0.2), "home")
    assert governor_scale([good] * 20) == 1.0
    assert governor_scale([bad] * 20) == 0.5
    # Old losses outside the trailing window are forgiven.
    assert governor_scale([bad] * 5 + [good] * 20, window=20) == 1.0


def test_ledger_persists_scores_and_feeds_lessons_summary(tmp_path: Path):
    path = tmp_path / "calibration.jsonl"
    ledger = CalibrationLedger(path)
    ledger.append(score_match(_forecast(model_home=0.2), "home"))
    reloaded = CalibrationLedger(path)
    assert len(reloaded.scores()) == 1
    assert reloaded.scale() == 0.5
    summary = summarise_scores(reloaded.scores())
    assert "Brier model" in summary
    assert "Governor delta-cap scale: 0.5" in summary


def test_empty_history_summarises_to_nothing():
    assert summarise_scores([]) == ""
    assert isinstance(MatchScore(match_id="x", date="d", outcome="home"), MatchScore)
