from __future__ import annotations

import numpy as np

from wolves.sim.tiebreaks import rank_group


def test_points_tied_pair_ordered_by_head_to_head_not_overall_gd():
    """Both tied pairs (6 pts and 3 pts) order by head-to-head against the overall-GD order."""
    pts = np.array([[6], [6], [3], [3]])
    gd = np.array([[5], [1], [-4], [-2]])
    gf = np.array([[6], [2], [1], [1]])

    h2h_pts = np.zeros((4, 4, 1), dtype=np.int16)
    h2h_gd = np.zeros((4, 4, 1), dtype=np.int16)
    h2h_gf = np.zeros((4, 4, 1), dtype=np.int16)

    def record(i: int, j: int, gi: int, gj: int) -> None:
        h2h_pts[i, j] += 3 if gi > gj else (1 if gi == gj else 0)
        h2h_pts[j, i] += 3 if gj > gi else (1 if gi == gj else 0)
        h2h_gd[i, j] += gi - gj
        h2h_gd[j, i] += gj - gi
        h2h_gf[i, j] += gi
        h2h_gf[j, i] += gj

    record(1, 0, 1, 0)
    record(0, 2, 4, 0)
    record(0, 3, 2, 0)
    record(1, 2, 1, 0)
    record(3, 1, 1, 0)
    record(2, 3, 1, 0)

    order = rank_group(np.random.default_rng(0), pts, gd, gf, h2h_pts, h2h_gd, h2h_gf)

    assert order[3, 0] == 1
    assert order[2, 0] == 0
    assert order[1, 0] == 2
    assert order[0, 0] == 3
