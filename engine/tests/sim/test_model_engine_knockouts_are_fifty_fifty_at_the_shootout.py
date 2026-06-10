from __future__ import annotations

from datetime import date

import numpy as np

from wolves.config import get_settings
from wolves.data.teams import registry_team_key
from wolves.models.contracts import FittedState
from wolves.sim.format import load_format
from wolves.sim.model_engine import PoissonMatchEngine

FMT = load_format(get_settings().data_dir)


def synthetic_state(strength_overrides: dict[str, float] | None = None) -> FittedState:
    keys = tuple(sorted(registry_team_key(team.id) for team in FMT.teams))
    strengths = np.array([(strength_overrides or {}).get(key, 0.0) for key in keys])
    return FittedState(
        model_id="test",
        version="0",
        dataset_version="test",
        as_of=date(2026, 6, 10),
        teams=keys,
        strengths=strengths,
        globals_={"intercept": float(np.log(1.3)), "home_adv": 0.25},
    )


def test_equal_sides_win_level_ties_half_the_time() -> None:
    engine = PoissonMatchEngine(FMT, synthetic_state())
    n = 40_000
    engine.begin(np.random.default_rng(1), n)
    home = np.zeros(n, dtype=np.intp)
    away = np.full(n, 1, dtype=np.intp)
    level = np.full(n, 1, dtype=np.int16)

    wins = engine.knockout_home_wins(np.random.default_rng(2), home, away, level, level, city=FMT.venues[0].city)

    assert abs(wins.mean() - 0.5) < 0.01


def test_stronger_side_keeps_only_its_extra_time_edge() -> None:
    strong = registry_team_key(FMT.teams[0].id)
    engine = PoissonMatchEngine(FMT, synthetic_state({strong: 0.3}))
    n = 40_000
    engine.begin(np.random.default_rng(1), n)
    home = np.zeros(n, dtype=np.intp)
    away = np.full(n, 1, dtype=np.intp)
    level = np.full(n, 0, dtype=np.int16)

    wins = engine.knockout_home_wins(np.random.default_rng(2), home, away, level, level, city=FMT.venues[0].city)

    # ET favours the stronger side, but the residual shootout mass is even.
    assert 0.52 < wins.mean() < 0.70


def test_decided_games_pass_through() -> None:
    engine = PoissonMatchEngine(FMT, synthetic_state())
    n = 100
    engine.begin(np.random.default_rng(1), n)
    home = np.zeros(n, dtype=np.intp)
    away = np.full(n, 1, dtype=np.intp)
    hg = np.full(n, 2, dtype=np.int16)
    ag = np.full(n, 1, dtype=np.int16)

    wins = engine.knockout_home_wins(np.random.default_rng(2), home, away, hg, ag, city=FMT.venues[0].city)

    assert wins.all()
