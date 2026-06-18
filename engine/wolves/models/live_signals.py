"""Blend live match signals into the pre-match goal rates that anchor the
in-match chain. Shots on target imply a current scoring pace; the blend shrinks
that pace into the pre-match lambda with a confidence weight that rises through
the match, capped so a freak early shot count cannot dominate. Possession adds a
small, confidence-weighted tilt. The blend acts on the rates before the chain's
score-state multipliers, so chasing behaviour is never double-counted."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

type Rates = float | np.ndarray


@dataclass(frozen=True)
class LiveSignals:
    """In-progress match observations, per side. Any field may be absent when
    the provider has not yet published it."""

    home_shots_on: int | None = None
    away_shots_on: int | None = None
    home_possession: float | None = None
    away_possession: float | None = None

    @property
    def has_shots(self) -> bool:
        return self.home_shots_on is not None and self.away_shots_on is not None

    @property
    def has_possession(self) -> bool:
        return self.home_possession is not None and self.away_possession is not None


@dataclass(frozen=True)
class BlendParams:
    # A 90-minute halflife caps live weight near half at full time, so a noisy early shot rate never dominates.
    halflife_minutes: float = 90.0
    conversion_prior: float = 0.30
    multiplier_cap: float = 2.0
    possession_tilt: float = 0.10


DEFAULT_BLEND = BlendParams()


def _confidence(minute: float, params: BlendParams) -> float:
    return minute / (minute + params.halflife_minutes)


def _shot_blend(lam: Rates, shots_on: int, minute: float, weight: float, params: BlendParams) -> Rates:
    live_rate = (shots_on / minute) * 90.0 * params.conversion_prior
    return weight * live_rate + (1.0 - weight) * lam


def _possession_tilt(possession: float, weight: float, params: BlendParams) -> float:
    return 1.0 + weight * params.possession_tilt * (2.0 * possession - 1.0)


def _side(
    lam: Rates,
    shots_on: int | None,
    possession: float | None,
    minute: float,
    weight: float,
    params: BlendParams,
) -> Rates:
    blended = lam if shots_on is None else _shot_blend(lam, shots_on, minute, weight, params)
    if possession is not None and params.possession_tilt > 0.0:
        blended = blended * _possession_tilt(possession, weight, params)
    return np.clip(blended, lam / params.multiplier_cap, lam * params.multiplier_cap)


def blend_rates(
    lam_home: Rates,
    lam_away: Rates,
    signals: LiveSignals,
    minute: float,
    *,
    params: BlendParams = DEFAULT_BLEND,
) -> tuple[Rates, Rates]:
    """Pre-match lambdas adjusted toward the live pace. Broadcasts over scalar
    rates or per-draw arrays alike. A no-op before kickoff or with no signals."""
    if minute <= 0.0 or not (signals.has_shots or signals.has_possession):
        return lam_home, lam_away
    weight = _confidence(minute, params)
    shots_home = signals.home_shots_on if signals.has_shots else None
    shots_away = signals.away_shots_on if signals.has_shots else None
    poss_home = signals.home_possession if signals.has_possession else None
    poss_away = signals.away_possession if signals.has_possession else None
    home = _side(lam_home, shots_home, poss_home, minute, weight, params)
    away = _side(lam_away, shots_away, poss_away, minute, weight, params)
    return home, away
