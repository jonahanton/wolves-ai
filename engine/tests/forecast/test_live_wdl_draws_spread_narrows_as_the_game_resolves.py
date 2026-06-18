from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from tests.sim.test_model_engine_knockouts_are_fifty_fifty_at_the_shootout import synthetic_state
from wolves.config import Settings
from wolves.data.teams import registry_team_key
from wolves.forecast import Forecaster
from wolves.models.inmatch import MatchState
from wolves.models.live_signals import LiveSignals

HOME, AWAY = "mexico", "south-africa"


@pytest.fixture()
def forecaster() -> Forecaster:
    base = synthetic_state()
    strengths = np.array(base.strengths, dtype=float)
    strengths[base.teams.index(registry_team_key(HOME))] = 0.4
    cov = np.eye(len(strengths) + 2) * 0.02
    instance = Forecaster(Settings(storage_mode="local"))
    instance._state = dataclasses.replace(base, strengths=strengths, covariance=cov)
    return instance


def _spread(
    forecaster: Forecaster, state: MatchState, *, knockout: bool = False
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    home, draw, away = forecaster.live_wdl_draws(HOME, AWAY, state, knockout=knockout, draws=200)
    return np.array(home), np.array(draw), np.array(away)


def test_each_draw_is_a_valid_wdl_split(forecaster: Forecaster) -> None:
    home, draw, away = _spread(forecaster, MatchState(minute=60.0, home_goals=1, away_goals=1))
    assert np.allclose(home + draw + away, 1.0)


def test_spread_centres_on_the_point_estimate(forecaster: Forecaster) -> None:
    state = MatchState(minute=80.0, home_goals=3, away_goals=2)
    home, _, _ = _spread(forecaster, state)
    point = forecaster.live_distribution(HOME, AWAY, state).p_home
    assert home.mean() == pytest.approx(point, abs=0.02)


def test_uncertainty_collapses_as_the_match_resolves(forecaster: Forecaster) -> None:
    early, _, _ = _spread(forecaster, MatchState(minute=0.0, home_goals=0, away_goals=0))
    late, _, _ = _spread(forecaster, MatchState(minute=83.0, home_goals=4, away_goals=2))
    assert late.std() < early.std()


def test_knockout_draws_carry_no_draw_mass(forecaster: Forecaster) -> None:
    _, draw, _ = _spread(forecaster, MatchState(minute=80.0, home_goals=0, away_goals=0), knockout=True)
    assert np.all(draw == 0.0)


def test_same_seed_is_deterministic(forecaster: Forecaster) -> None:
    state = MatchState(minute=70.0, home_goals=1, away_goals=0)
    first = forecaster.live_wdl_draws(HOME, AWAY, state, knockout=False, seed=0, draws=64)
    second = forecaster.live_wdl_draws(HOME, AWAY, state, knockout=False, seed=0, draws=64)
    assert first == second


def test_live_shot_dominance_moves_the_per_draw_spread(forecaster: Forecaster) -> None:
    """The blend must reach the per-draw arrays, not just the scalar rate: a side
    out-shooting the other lifts its win mass across the whole spread."""
    state = MatchState(minute=60.0, home_goals=0, away_goals=0)
    base_home, _, _ = _spread(forecaster, state)
    signals = LiveSignals(home_shots_on=8, away_shots_on=1)
    blended_home, _, blended_away = forecaster.live_wdl_draws(
        HOME, AWAY, state, knockout=False, draws=200, signals=signals
    )
    assert np.array(blended_home).mean() > base_home.mean() + 0.05
    assert np.array(blended_home).mean() > np.array(blended_away).mean()


def test_replay_blends_only_the_live_minute_not_earlier_keyframes(forecaster: Forecaster) -> None:
    """A replay's earlier keyframes keep their pure pre-match anchor; only the
    latest state carries the current live signal."""
    early = MatchState(minute=20.0, home_goals=0, away_goals=0)
    now = MatchState(minute=75.0, home_goals=0, away_goals=0)
    signals = LiveSignals(home_shots_on=9, away_shots_on=1)
    base = forecaster.live_wdl_draws_at(HOME, AWAY, [early, now], knockout=False, draws=128)
    blended = forecaster.live_wdl_draws_at(HOME, AWAY, [early, now], knockout=False, draws=128, signals=signals)
    assert blended[0] == base[0]
    assert np.mean(blended[1][0]) > np.mean(base[1][0])
