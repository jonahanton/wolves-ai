"""Proper scores over W/D/L probability triplets."""

from __future__ import annotations

import numpy as np

EPS = 1e-12


def log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    picked = probs[np.arange(outcomes.shape[0]), outcomes]
    return -float(np.mean(np.log(np.clip(picked, EPS, None))))


def rank_probability_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    cumulative = np.cumsum(probs, axis=1)
    observed = np.cumsum(np.eye(3)[outcomes], axis=1)
    return float(np.mean(np.sum((cumulative - observed) ** 2, axis=1) / 2.0))
