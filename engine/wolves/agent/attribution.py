"""Decompose a day-on-day forecast move into its deterministic channels.

The dry runs proved the bracket overlay and the refit are BOTH material
(one group win is ~+0.8pp through the bracket and ~+0.9pp through
strengths), so the report separates them; what the channels leave is the
agent's to justify."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from wolves.forecast import Forecaster
from wolves.sim.format import PlayedResult


class AttributionReport(BaseModel):
    as_of: str
    previous_as_of: str
    bracket_pp: dict[str, float] = Field(default_factory=dict)
    refit_pp: dict[str, float] = Field(default_factory=dict)
    residual_pp: dict[str, float] = Field(default_factory=dict)


def decompose(
    forecaster: Forecaster,
    *,
    as_of: date,
    previous_as_of: date,
    results: dict[int, PlayedResult] | None = None,
    submitted: dict[str, float] | None = None,
    n_sims: int = 50_000,
    seed: int = 0,
    floor_pp: float = 0.2,
) -> AttributionReport:
    """Per-team title deltas split into the bracket-overlay channel (new
    results through yesterday's strengths) and the refit channel (today's
    strengths); the residual against the submitted numbers is the agent's
    evidence-driven move."""
    forecaster.fit(as_of=as_of)
    today = forecaster.title_probs(n_sims=n_sims, seed=seed, results=results)
    forecaster.fit(as_of=previous_as_of)
    yesterday = forecaster.title_probs(n_sims=n_sims, seed=seed)
    overlaid = forecaster.title_probs(n_sims=n_sims, seed=seed, results=results) if results else yesterday
    # Leave the forecaster on today's state; refits are deterministic and cheap.
    forecaster.fit(as_of=as_of)

    def diff(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
        deltas = {t: round((a.get(t, 0.0) - b.get(t, 0.0)) * 100, 2) for t in a}
        return {t: d for t, d in sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True) if abs(d) >= floor_pp}

    residual: dict[str, float] = {}
    if submitted is not None:
        residual = diff(submitted, today)
    return AttributionReport(
        as_of=as_of.isoformat(),
        previous_as_of=previous_as_of.isoformat(),
        bracket_pp=diff(overlaid, yesterday),
        refit_pp=diff(today, overlaid),
        residual_pp=residual,
    )
