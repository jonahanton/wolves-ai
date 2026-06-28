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
    """Order group teams (best last): points, overall GD, overall goals, head-to-head,
    then lots (FIFA Article 13.2).

    Lots stand in for fair play points; head-to-head is taken over the points-tied set,
    which differs from FIFA's shrinking-subset re-application only in rare partial splits.
    """
    tied = pts[:, None, :] == pts[None, :, :]
    keys = (
        rng.random(pts.shape),
        (h2h_gf * tied).sum(axis=1),
        (h2h_gd * tied).sum(axis=1),
        (h2h_pts * tied).sum(axis=1),
        gf,
        gd,
        pts,
    )
    return np.lexsort(keys, axis=0)


def rank_thirds(rng: np.random.Generator, pts: np.ndarray, gd: np.ndarray, gf: np.ndarray) -> np.ndarray:
    """Order third-placed teams (best last): points, GD, goals, drawn lots."""
    return np.lexsort((rng.random(pts.shape), gf, gd, pts), axis=0)
