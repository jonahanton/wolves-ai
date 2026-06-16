"""Publish-time anchoring: extremising and the trust governor share one
log-odds blend. d = 1.0 publishes the agent's numbers untouched; the
governor shrinks d towards the deterministic baseline when the trailing
adjustment PnL is negative, loudly recorded in the snapshot."""

from __future__ import annotations

import math


def blend_log_odds(
    agent: dict[str, float], anchor: dict[str, float], *, d: float, renormalise: bool = False
) -> dict[str, float]:
    """log O_pub = log O_anchor + d (log O_agent - log O_anchor).

    Renormalise only when the dict is an exhaustive partition (the title
    distribution); marginal probabilities blend stage by stage untouched."""
    if d == 1.0:
        return dict(agent)
    blended: dict[str, float] = {}
    for team, p_agent in agent.items():
        p_anchor = anchor.get(team, p_agent)
        blended[team] = _from_log_odds(_log_odds(p_anchor) + d * (_log_odds(p_agent) - _log_odds(p_anchor)))
    if renormalise:
        total = sum(blended.values())
        if total > 0:
            blended = {team: p / total for team, p in blended.items()}
    return blended


def longshot_shade(titles: dict[str, float], *, alpha: float) -> dict[str, float]:
    """Favourite-longshot correction: raise each probability to (1 + alpha),
    renormalise. alpha=0 is the identity; alpha>0 shaves probability off
    longshots and gives it to favourites, the share monotone in the input."""
    if alpha == 0.0 or not titles:
        return dict(titles)
    powered = {team: max(p, 0.0) ** (1.0 + alpha) for team, p in titles.items()}
    total = sum(powered.values())
    if total <= 0:
        return dict(titles)
    return {team: p / total for team, p in powered.items()}


def publish_scale(*, extremising_d: float, governor_scale: float, shrink_weight: float) -> float:
    """The effective d at publish time: extremising tempered by the governor."""
    if governor_scale >= 1.0:
        return extremising_d
    return extremising_d * shrink_weight


def _log_odds(p: float) -> float:
    clamped = min(max(p, 1e-9), 1.0 - 1e-9)
    return math.log(clamped / (1.0 - clamped))


def _from_log_odds(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))
