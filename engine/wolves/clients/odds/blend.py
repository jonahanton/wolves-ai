"""Shrink model abilities toward market-implied abilities.

Market outright probabilities are mapped onto the Elo scale through the
logistic Elo relation (one logit is 400/ln(10) Elo points), centred on the
mean of the model's own ratings over the teams the market prices. This is a
monotone anchor, not a structural inversion of the tournament; its job is to
pull gross model-vs-market divergence in, with fixed lambda.
"""

from __future__ import annotations

import math

ELO_PER_LOGIT = 400.0 / math.log(10.0)


def _logit(p: float) -> float:
    p = min(max(p, 1e-9), 1.0 - 1e-9)
    return math.log(p / (1.0 - p))


def market_implied_abilities(
    market_probs: dict[str, float],
    *,
    anchor: dict[str, float],
) -> dict[str, float]:
    """Map outright probabilities onto the Elo scale, centred on the anchor mean."""
    common = [team for team in market_probs if team in anchor]
    if not common:
        return {}
    anchor_mean = sum(anchor[t] for t in common) / len(common)
    logits = {t: _logit(market_probs[t]) for t in common}
    logit_mean = sum(logits.values()) / len(logits)
    return {t: anchor_mean + (logits[t] - logit_mean) * ELO_PER_LOGIT for t in common}


def blend_abilities(
    model: dict[str, float],
    market_probs: dict[str, float],
    *,
    lam: float,
) -> dict[str, float]:
    """Linear blend of model abilities toward market-implied abilities.

    Teams the market does not price keep their model ability unchanged.
    """
    implied = market_implied_abilities(market_probs, anchor=model)
    return {team: (1.0 - lam) * elo + lam * implied[team] if team in implied else elo for team, elo in model.items()}
