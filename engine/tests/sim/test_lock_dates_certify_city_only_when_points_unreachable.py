from __future__ import annotations

import numpy as np
import pytest

from wolves.config import Settings
from wolves.sim.engine import EloMatchEngine
from wolves.sim.format import PlayedResult, load_format
from wolves.sim.mc import run_tournament
from wolves.sim.outputs import build_focus_team


@pytest.fixture(scope="module")
def fmt():
    return load_format(Settings().data_dir)


def _focus_locks(fmt, results):
    base = np.full(48, 1800.0)
    result = run_tournament(fmt, EloMatchEngine(fmt, base), n_sims=400, seed=5, results=results)
    return build_focus_team(fmt, result, team_id="england").lock_dates


def test_six_points_with_rivals_on_two_locks_atlanta_after_matchday_two(fmt):
    results = {
        21: PlayedResult(match=21, home_goals=0, away_goals=0),
        22: PlayedResult(match=22, home_goals=2, away_goals=0),
        45: PlayedResult(match=45, home_goals=1, away_goals=0),
        46: PlayedResult(match=46, home_goals=1, away_goals=1),
    }
    locks = _focus_locks(fmt, results)
    assert locks[1].prob_locked == 1.0
    assert locks[1].locked_city_probs == {"Atlanta": 1.0}


def test_nothing_locks_after_matchday_one_and_group_end_resolves_everything(fmt):
    locks = _focus_locks(fmt, {})
    assert locks[0].prob_locked == 0.0
    assert locks[-1].prob_locked == 1.0
    assert set(locks[-1].locked_city_probs) == {"Atlanta", "Toronto", "Kansas City"}


def test_a_loss_on_matchday_two_cannot_lock_anything(fmt):
    results = {
        21: PlayedResult(match=21, home_goals=0, away_goals=0),
        22: PlayedResult(match=22, home_goals=2, away_goals=0),
        45: PlayedResult(match=45, home_goals=0, away_goals=1),
        46: PlayedResult(match=46, home_goals=1, away_goals=1),
    }
    locks = _focus_locks(fmt, results)
    assert locks[1].prob_locked == 0.0
