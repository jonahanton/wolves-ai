"""The published number: a convex blend of champion simulation and de-vigged
market consensus, with the weight fitted on the backtest."""

from __future__ import annotations

import numpy as np

WEIGHT_GRID = np.linspace(0.0, 1.0, 101)


def blend_probabilities(model: dict[str, float], market: dict[str, float], *, model_weight: float) -> dict[str, float]:
    """Probability-space convex blend over the union of outcomes, renormalised."""
    names = sorted(model.keys() | market.keys())
    mixed = {n: model_weight * model.get(n, 0.0) + (1.0 - model_weight) * market.get(n, 0.0) for n in names}
    total = sum(mixed.values())
    return {n: p / total for n, p in mixed.items()} if total > 0 else {}


def fit_model_weight(samples: list[tuple[np.ndarray, np.ndarray, int]]) -> tuple[float, float]:
    """Grid-fit the model weight minimising log loss over (model, market, outcome)
    samples; returns (weight, log_loss_at_weight)."""
    model = np.array([s[0] for s in samples])
    market = np.array([s[1] for s in samples])
    outcomes = np.array([s[2] for s in samples])
    picked_model = model[np.arange(len(samples)), outcomes]
    picked_market = market[np.arange(len(samples)), outcomes]
    losses = [
        -float(np.mean(np.log(np.clip(w * picked_model + (1.0 - w) * picked_market, 1e-12, None)))) for w in WEIGHT_GRID
    ]
    best = int(np.argmin(losses))
    return float(WEIGHT_GRID[best]), losses[best]
