"""Power-method de-vig and log-odds consensus.

The power method removes the bookmaker margin by solving for k such that
sum(q_i^k) = 1 where q_i = 1/price. Unlike proportional normalisation it
corrects favourite-longshot bias, shrinking longshots harder. Consensus
across bookmakers averages in log-odds space, which weights books with
extreme views less than a linear average would.
"""

from __future__ import annotations

import math
from collections import defaultdict


class DevigError(ValueError):
    def __init__(self, prices: list[float]) -> None:
        self.prices = prices
        super().__init__(f"cannot de-vig prices {prices!r}: all must be > 1.0")


def power_devig(prices: list[float], *, tol: float = 1e-10, max_iter: int = 200) -> list[float]:
    """Convert decimal prices for one market into margin-free probabilities."""
    if not prices or any(p <= 1.0 for p in prices):
        raise DevigError(prices)
    implied = [1.0 / p for p in prices]

    def overround(k: float) -> float:
        return sum(q**k for q in implied) - 1.0

    lo, hi = 0.5, 1.0
    while overround(hi) > 0:
        hi *= 2.0
        if hi > 1e6:
            raise DevigError(prices)
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if overround(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    k = (lo + hi) / 2.0
    probs = [q**k for q in implied]
    total = sum(probs)
    return [p / total for p in probs]


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1.0 - 1e-9)
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def consensus_probabilities(per_book: list[dict[str, float]]) -> dict[str, float]:
    """Average de-vigged probabilities across bookmakers in log-odds space.

    Each dict maps outcome name to probability from one bookmaker. Outcomes
    missing from a book are skipped for that book. The result is renormalised
    to sum to 1 over the union of outcomes.
    """
    logits: dict[str, list[float]] = defaultdict(list)
    for book in per_book:
        for name, prob in book.items():
            logits[name].append(_logit(prob))
    if not logits:
        return {}
    averaged = {name: _sigmoid(sum(values) / len(values)) for name, values in logits.items()}
    total = sum(averaged.values())
    return {name: p / total for name, p in averaged.items()}


def weighted_consensus(legs: list[tuple[dict[str, float], float]]) -> dict[str, float]:
    """Blend probability legs (e.g. bookmaker consensus and a prediction
    market) by weighted log-odds average, renormalised to sum to 1.

    Outcomes missing from a leg are skipped for that leg; legs with
    non-positive weight are ignored entirely.
    """
    sums: dict[str, float] = defaultdict(float)
    weights: dict[str, float] = defaultdict(float)
    for probs, weight in legs:
        if weight <= 0.0:
            continue
        for name, prob in probs.items():
            sums[name] += weight * _logit(prob)
            weights[name] += weight
    if not sums:
        return {}
    averaged = {name: _sigmoid(sums[name] / weights[name]) for name in sums}
    total = sum(averaged.values())
    return {name: p / total for name, p in averaged.items()}
