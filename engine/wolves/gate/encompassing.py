"""Promotion by encompassing: does the optimal convex blend of market and
challenger put significantly nonzero weight on the challenger? Significance
uses a Diebold-Mariano paired test with the Harvey-Leybourne-Newbold
small-sample correction."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel
from scipy.stats import t as student_t

from wolves.gate.scoring import EPS, log_loss, rank_probability_score
from wolves.markets.blend import fit_model_weight


class EncompassingResult(BaseModel):
    n_matches: int
    model_log_loss: float
    market_log_loss: float
    blend_weight: float
    blend_log_loss: float
    model_rps: float
    market_rps: float
    p_value: float

    @property
    def significant(self) -> bool:
        return self.blend_weight > 0.0 and self.p_value < 0.05


def hln_p_value(loss_market: np.ndarray, loss_blend: np.ndarray) -> float:
    """One-sided p for the blend improving on the market alone."""
    diff = loss_market - loss_blend
    n = diff.shape[0]
    mean = float(diff.mean())
    se = float(diff.std(ddof=1)) / np.sqrt(n)
    if se == 0.0:
        return 1.0
    # HLN small-sample factor at forecast horizon h=1.
    correction = np.sqrt((n - 1) / n)
    statistic = correction * mean / se
    return float(1.0 - student_t.cdf(statistic, df=n - 1))


def encompassing_test(model: np.ndarray, market: np.ndarray, outcomes: np.ndarray) -> EncompassingResult:
    samples = [(model[i], market[i], int(outcomes[i])) for i in range(outcomes.shape[0])]
    weight, blend_ll = fit_model_weight(samples)
    blended = weight * model + (1.0 - weight) * market
    picked = np.arange(outcomes.shape[0]), outcomes
    loss_market = -np.log(np.clip(market[picked], EPS, None))
    loss_blend = -np.log(np.clip(blended[picked], EPS, None))
    return EncompassingResult(
        n_matches=outcomes.shape[0],
        model_log_loss=log_loss(model, outcomes),
        market_log_loss=log_loss(market, outcomes),
        blend_weight=weight,
        blend_log_loss=blend_ll,
        model_rps=rank_probability_score(model, outcomes),
        market_rps=rank_probability_score(market, outcomes),
        p_value=hln_p_value(loss_market, loss_blend),
    )
