"""Scenario digests: a perturbation set against the baseline, as deltas."""

from __future__ import annotations

from pydantic import BaseModel

from wolves.forecast import DEFAULT_SIMS, Forecaster, Perturbation
from wolves.models.contracts import ScorelineDistribution
from wolves.sim.format import PlayedResult
from wolves.sim.outputs import build_team_reach

MOVER_THRESHOLD_PP = 0.2


class TeamDelta(BaseModel):
    team: str
    baseline: float
    scenario: float
    delta_pp: float


class ScenarioResult(BaseModel):
    n_sims: int
    seed: int
    perturbations: list[str]
    title_movers: list[TeamDelta]
    r32_movers: list[TeamDelta]


def _movers(
    baseline: dict[str, dict[str, float]], scenario: dict[str, dict[str, float]], round_: str
) -> list[TeamDelta]:
    deltas = [
        TeamDelta(
            team=team,
            baseline=baseline[team][round_],
            scenario=scenario[team][round_],
            delta_pp=round((scenario[team][round_] - baseline[team][round_]) * 100.0, 2),
        )
        for team in baseline
    ]
    return sorted((d for d in deltas if abs(d.delta_pp) >= MOVER_THRESHOLD_PP), key=lambda d: -abs(d.delta_pp))


def run_scenario(
    forecaster: Forecaster,
    perturbations: tuple[Perturbation, ...],
    *,
    results: dict[int, PlayedResult] | None = None,
    live_distributions: dict[int, ScorelineDistribution] | None = None,
    n_sims: int = DEFAULT_SIMS,
    seed: int = 0,
) -> ScenarioResult:
    """Common random numbers (one seed) keep the delta noise-free."""
    base = build_team_reach(
        forecaster.fmt,
        forecaster.simulate(n_sims=n_sims, seed=seed, results=results, parameter_uncertainty=False),
    )
    perturbed = build_team_reach(
        forecaster.fmt,
        forecaster.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=perturbations,
            results=results,
            live_distributions=live_distributions,
            parameter_uncertainty=False,
        ),
    )
    return ScenarioResult(
        n_sims=n_sims,
        seed=seed,
        perturbations=[repr(p) for p in perturbations],
        title_movers=_movers(base, perturbed, "champion"),
        r32_movers=_movers(base, perturbed, "r32"),
    )
