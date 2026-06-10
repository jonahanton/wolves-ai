from __future__ import annotations

import numpy as np

from wolves.config import get_settings
from wolves.models.contracts import MAX_GOALS, ScorelineDistribution
from wolves.sim.engine import EloMatchEngine
from wolves.sim.format import load_format
from wolves.sim.mc import run_tournament


def test_an_injected_in_progress_score_constrains_every_world() -> None:
    fmt = load_format(get_settings().data_dir)
    base = np.full(len(fmt.teams), 1800.0)
    grid = np.zeros((MAX_GOALS + 1, MAX_GOALS + 1))
    grid[5, 0] = 1.0
    first = sorted(fmt.group_matches, key=lambda m: m.date)[0]

    result = run_tournament(
        fmt,
        EloMatchEngine(fmt, base),
        n_sims=300,
        seed=3,
        live_distributions={first.match: ScorelineDistribution(grid=grid)},
    )

    hg, ag = result.group_goals[first.match]
    assert (hg == 5).all()
    assert (ag == 0).all()
