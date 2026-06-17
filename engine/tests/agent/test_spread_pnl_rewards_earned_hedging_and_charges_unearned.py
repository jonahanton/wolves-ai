from __future__ import annotations

import pytest

from wolves.agent.calibration import MatchForecast, WorldProbs, score_match, spread_pnl, summarise_scores

MODAL = WorldProbs(weight=0.7, probs={"home": 0.7, "draw": 0.2, "away": 0.1})
HEDGE = WorldProbs(weight=0.3, probs={"home": 0.2, "draw": 0.3, "away": 0.5})


@pytest.mark.parametrize(
    ("worlds", "outcome", "expectation"),
    [
        ([MODAL, HEDGE], "away", "positive"),
        ([MODAL, HEDGE], "home", "negative"),
        ([MODAL], "home", "none"),
        ([], "home", "none"),
    ],
)
def test_spread_pnl_sign_tracks_where_the_outcome_landed(worlds, outcome, expectation):
    pnl = spread_pnl(worlds, outcome)
    if expectation == "none":
        assert pnl is None
    elif expectation == "positive":
        assert pnl is not None and pnl > 0.0
    else:
        assert pnl is not None and pnl < 0.0


def test_score_match_carries_spread_pnl_and_summary_mentions_it():
    forecast = MatchForecast(
        match_id="m1",
        date="2026-06-17",
        home="england",
        away="croatia",
        model_probs={"home": 0.55, "draw": 0.23, "away": 0.22},
        world_probs=[MODAL, HEDGE],
    )
    score = score_match(forecast, "away")
    assert score.spread_pnl == pytest.approx(spread_pnl([MODAL, HEDGE], "away"))
    summary = summarise_scores([score])
    assert "Spread P&L over 1 matches" in summary


def test_single_world_summary_stays_silent_on_spread():
    forecast = MatchForecast(
        match_id="m1",
        date="2026-06-17",
        home="england",
        away="croatia",
        model_probs={"home": 0.55, "draw": 0.23, "away": 0.22},
        world_probs=[MODAL],
    )
    score = score_match(forecast, "home")
    assert score.spread_pnl is None
    assert "Spread P&L" not in summarise_scores([score])
