from __future__ import annotations

import pytest

from wolves.sim.api import run_simulation


def test_same_seed_reproduces_the_exact_output():
    a = run_simulation({}, {}, 1500, 123)
    b = run_simulation({}, {}, 1500, 123)
    assert a.model_dump() == b.model_dump()


def test_positive_rating_override_raises_champion_probability():
    base = run_simulation({}, {}, 8000, 123)
    boosted = run_simulation({"england": 120.0}, {}, 8000, 123)
    eng = {t.team_id: t.champion_prob for t in base.teams}["england"]
    eng_boosted = {t.team_id: t.champion_prob for t in boosted.teams}["england"]
    assert eng_boosted > eng


def test_champion_probabilities_sum_to_one():
    out = run_simulation({}, {}, 3000, 9)
    assert sum(t.champion_prob for t in out.teams) == pytest.approx(1.0, abs=0.01)
