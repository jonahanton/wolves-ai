from __future__ import annotations

import numpy as np

from wolves.sim.tiebreaks import rank_group


def test_points_tied_pair_ordered_by_overall_gd_not_head_to_head():
    """FIFA Article 13.2 ranks points-level teams by overall goal difference before
    head-to-head, so the better overall GD outranks the side that won the meeting."""
    pts = np.array([[4], [4], [3], [0]])
    gd = np.array([[1], [3], [-1], [-3]])
    gf = np.array([[2], [4], [2], [1]])

    h2h_pts = np.zeros((4, 4, 1), dtype=np.int16)
    h2h_gd = np.zeros((4, 4, 1), dtype=np.int16)
    h2h_gf = np.zeros((4, 4, 1), dtype=np.int16)
    # Team 0 beat team 1 head-to-head, yet team 1 has the better overall GD.
    h2h_pts[0, 1], h2h_pts[1, 0] = 3, 0
    h2h_gd[0, 1], h2h_gd[1, 0] = 2, -2
    h2h_gf[0, 1], h2h_gf[1, 0] = 2, 0

    order = rank_group(np.random.default_rng(0), pts, gd, gf, h2h_pts, h2h_gd, h2h_gf)

    assert order[3, 0] == 1
    assert order[2, 0] == 0
    assert order[1, 0] == 2
    assert order[0, 0] == 3
