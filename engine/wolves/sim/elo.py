from __future__ import annotations

import numpy as np

BASE_K = 32.0
STAGE_K_MULT = {"group": 1.6, "knockout": 1.76}
_MAX_MARGIN = 15
_HARMONIC = np.cumsum(1.0 / np.arange(1, _MAX_MARGIN + 1))


def expected_score(diff: np.ndarray) -> np.ndarray:
    """Elo win expectancy for the side `diff` rating points stronger."""
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def harmonic_margin(margin: np.ndarray) -> np.ndarray:
    """Margin multiplier where the second goal is worth 1/2 and the third 1/3."""
    return _HARMONIC[np.clip(np.abs(margin), 1, _MAX_MARGIN) - 1]


def rating_delta(diff: np.ndarray, goals_a: np.ndarray, goals_b: np.ndarray, *, stage: str) -> np.ndarray:
    """Rating change for side A given the effective pre-match diff (HFA included)."""
    result = np.where(goals_a > goals_b, 1.0, np.where(goals_a == goals_b, 0.5, 0.0))
    k = BASE_K * STAGE_K_MULT[stage]
    return k * harmonic_margin(goals_a - goals_b) * (result - expected_score(diff))
