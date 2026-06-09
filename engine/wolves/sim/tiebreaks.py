from __future__ import annotations

import numpy as np


def rank_group(
    rng: np.random.Generator,
    pts: np.ndarray,
    gd: np.ndarray,
    gf: np.ndarray,
    h2h_pts: np.ndarray,
    h2h_gd: np.ndarray,
    h2h_gf: np.ndarray,
) -> np.ndarray:
    """Order group teams (best last): points, head-to-head among points-tied teams, GD, goals, lots.

    Drawn lots stand in for fair play points until booking data exists.
    Head-to-head stats are restricted once to the points-tied set; FIFA's
    re-application to shrinking subsets differs only in rare partial-split ties.
    """
    tied = pts[:, None, :] == pts[None, :, :]
    keys = (
        rng.random(pts.shape),
        gf,
        gd,
        (h2h_gf * tied).sum(axis=1),
        (h2h_gd * tied).sum(axis=1),
        (h2h_pts * tied).sum(axis=1),
        pts,
    )
    return np.lexsort(keys, axis=0)


def rank_thirds(rng: np.random.Generator, pts: np.ndarray, gd: np.ndarray, gf: np.ndarray) -> np.ndarray:
    """Order third-placed teams (best last): points, GD, goals, drawn lots."""
    return np.lexsort((rng.random(pts.shape), gf, gd, pts), axis=0)
