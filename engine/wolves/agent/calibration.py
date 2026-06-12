"""Calibration ledger: proper scores against baselines, adjustment P&L and
the governor that halves delta caps when adjustments lose money."""

from __future__ import annotations

import math
from pathlib import Path

from pydantic import BaseModel, Field

OUTCOMES = ("home", "draw", "away")
_UNIFORM = {o: 1.0 / 3.0 for o in OUTCOMES}


class WorldProbs(BaseModel):
    weight: float
    probs: dict[str, float]


class MatchForecast(BaseModel):
    match_id: str
    date: str
    home: str
    away: str
    model_probs: dict[str, float]
    market_probs: dict[str, float] | None = None
    frozen_sim_probs: dict[str, float] | None = None
    adjusted: bool = False
    world_probs: list[WorldProbs] = Field(default_factory=list)


class MatchScore(BaseModel):
    match_id: str
    date: str
    outcome: str
    brier: dict[str, float] = Field(default_factory=dict)
    log_loss: dict[str, float] = Field(default_factory=dict)
    adjustment_pnl: float | None = None
    spread_pnl: float | None = None


def brier_score(probs: dict[str, float], outcome: str) -> float:
    return sum((probs.get(o, 0.0) - (1.0 if o == outcome else 0.0)) ** 2 for o in OUTCOMES)


def log_loss(probs: dict[str, float], outcome: str) -> float:
    return -math.log(max(probs.get(outcome, 0.0), 1e-9))


def ranked_probability_score(probs: dict[str, float], outcome: str) -> float:
    """RPS over the ordered (home, draw, away) scale; the last cumulative term is always zero."""
    cdf = 0.0
    observed = 0.0
    total = 0.0
    for o in OUTCOMES[:-1]:
        cdf += probs.get(o, 0.0)
        observed += 1.0 if o == outcome else 0.0
        total += (cdf - observed) ** 2
    return total


def spread_pnl(worlds: list[WorldProbs], outcome: str) -> float | None:
    """RPS the modal (max-weight) world would have scored minus the mixture's
    RPS, so positive means hedging across worlds was earned.

    RPS on W/D/L stands in for CRPS on goal difference: the W/D/L
    probabilities are the published, scored surface, while per-world
    goal-difference distributions are never published. A single world or a
    degenerate weight vector prices no spread, so the P&L is None, never 0."""
    if len(worlds) < 2:
        return None
    total_weight = sum(w.weight for w in worlds)
    if total_weight <= 0.0:
        return None
    mixture = {o: sum(w.weight * w.probs.get(o, 0.0) for w in worlds) / total_weight for o in OUTCOMES}
    modal = max(worlds, key=lambda w: w.weight)
    return ranked_probability_score(modal.probs, outcome) - ranked_probability_score(mixture, outcome)


def score_match(forecast: MatchForecast, outcome: str) -> MatchScore:
    """Score one resolved match against uniform, market and frozen-sim baselines.

    Adjustment P&L is the log-loss saved versus the frozen no-agent sim, so
    positive means the agent's adjustments helped."""
    candidates = {
        "model": forecast.model_probs,
        "uniform": _UNIFORM,
        "market": forecast.market_probs,
        "frozen_sim": forecast.frozen_sim_probs,
    }
    briers = {name: brier_score(probs, outcome) for name, probs in candidates.items() if probs is not None}
    losses = {name: log_loss(probs, outcome) for name, probs in candidates.items() if probs is not None}
    pnl: float | None = None
    if forecast.adjusted and forecast.frozen_sim_probs is not None:
        pnl = losses["frozen_sim"] - losses["model"]
    return MatchScore(
        match_id=forecast.match_id,
        date=forecast.date,
        outcome=outcome,
        brier=briers,
        log_loss=losses,
        adjustment_pnl=pnl,
        spread_pnl=spread_pnl(forecast.world_probs, outcome),
    )


def governor_scale(scores: list[MatchScore], *, window: int = 20) -> float:
    """Halve the delta caps when adjustment P&L over the trailing window of
    adjusted matches is negative; otherwise full caps."""
    adjusted = [s.adjustment_pnl for s in scores if s.adjustment_pnl is not None]
    trailing = adjusted[-window:]
    if trailing and sum(trailing) < 0.0:
        return 0.5
    return 1.0


def total_spread_pnl(scores: list[MatchScore], *, window: int = 20) -> float | None:
    """Trailing-window spread P&L for the calibration block; None when no
    scored match carried per-world probabilities."""
    spreads = [s.spread_pnl for s in scores[-window:] if s.spread_pnl is not None]
    if not spreads:
        return None
    return sum(spreads)


def summarise_scores(scores: list[MatchScore], *, window: int = 20) -> str:
    """One-paragraph scorecard for LESSONS.md."""
    if not scores:
        return ""
    recent = scores[-window:]

    def mean(name: str) -> float | None:
        values = [s.brier[name] for s in recent if name in s.brier]
        return sum(values) / len(values) if values else None

    parts = [f"Scored {len(recent)} recent matches."]
    for name in ("model", "market", "frozen_sim", "uniform"):
        value = mean(name)
        if value is not None:
            parts.append(f"Brier {name}: {value:.3f}.")
    pnls = [s.adjustment_pnl for s in recent if s.adjustment_pnl is not None]
    if pnls:
        parts.append(f"Adjustment P&L over {len(pnls)} adjusted matches: {sum(pnls):+.3f} log-loss saved.")
        parts.append(f"Governor delta-cap scale: {governor_scale(scores, window=window):.1f}.")
    spreads = [s.spread_pnl for s in recent if s.spread_pnl is not None]
    if spreads:
        parts.append(f"Spread P&L over {len(spreads)} matches: {sum(spreads):+.3f} RPS saved by hedging.")
    return " ".join(parts)


class CalibrationLedger:
    """Append-only JSONL of match scores at a stable cross-run path."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._scores: list[MatchScore] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._scores.append(MatchScore.model_validate_json(line))

    def append(self, score: MatchScore) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(score.model_dump_json() + "\n")
        self._scores.append(score)

    def scores(self) -> list[MatchScore]:
        return list(self._scores)

    def scale(self, *, window: int = 20) -> float:
        return governor_scale(self._scores, window=window)
