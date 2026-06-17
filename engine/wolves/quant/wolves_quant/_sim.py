from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from wolves.forecast import Perturbation, StrengthPerturbation
from wolves.quant.wolves_quant._state import SESSION, context, forecaster

if TYPE_CHECKING:
    import pandas as pd

    from wolves.sim.latent import LatentEffect

_MANAGED_LOAD_RE = re.compile(
    r"\b(load[- ]managed|load[- ]management|managed[- ]load|minutes?[- ](?:managed|limited|restriction))\b",
    re.IGNORECASE,
)


def _validate_quant_perturbations(perturbations: tuple[Perturbation, ...]) -> None:
    for perturbation in perturbations:
        if isinstance(perturbation, StrengthPerturbation) and _MANAGED_LOAD_RE.search(perturbation.reason):
            raise ValueError(
                "managed-load availability cannot be priced as a full-tournament StrengthPerturbation "
                "inside the quant workbench; use a match-specific MatchRatePerturbation, or leave it "
                "unpriced when the evidence ceiling is zero or below the noise floor"
            )


def _n_sims(n_sims: int | None) -> int:
    return n_sims or context().default_n_sims


def _tournament_team_ids() -> list[str]:
    return [team.id for team in forecaster().fmt.teams]


def _checked_tournament_teams(teams: list[str] | None) -> list[str]:
    allowed = _tournament_team_ids()
    if teams is None:
        return allowed
    bad = sorted(set(teams) - set(allowed))
    if bad:
        from wolves.quant.wolves_quant._state import SandboxContextError

        raise SandboxContextError(
            f"tournament team(s) {', '.join(bad)}",
            f"use ids from wq.teams(); valid ids include {', '.join(allowed[:8])}",
        )
    return teams


def baseline(*, n_sims: int | None = None, seed: int = 0) -> dict[str, float]:
    """Unperturbed title probabilities, cached per (n_sims, seed)."""
    n = _n_sims(n_sims)
    key = (n, seed)
    if key not in SESSION.baselines:
        SESSION.baselines[key] = forecaster().title_probs(n_sims=n, seed=seed)
        SESSION.usage.sims += 1
    return SESSION.baselines[key]


def simulate(
    perturbations: tuple[Perturbation, ...] | list[Perturbation] = (),
    *,
    latent_effects: tuple[LatentEffect, ...] | list[LatentEffect] = (),
    n_sims: int | None = None,
    seed: int = 0,
) -> dict[str, float]:
    """Title probabilities under perturbations, common random numbers by seed."""
    perturbations = tuple(perturbations)
    _validate_quant_perturbations(perturbations)
    SESSION.usage.sims += 1
    return forecaster().title_probs(
        n_sims=_n_sims(n_sims), seed=seed, perturbations=perturbations, latent_effects=tuple(latent_effects)
    )


def reach(
    perturbations: tuple[Perturbation, ...] | list[Perturbation] = (),
    *,
    n_sims: int | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-team reach probabilities through the rounds (rows teams, columns
    r32 to champion), common random numbers by seed."""
    import pandas as pd

    perturbations = tuple(perturbations)
    _validate_quant_perturbations(perturbations)
    SESSION.usage.sims += 1
    outputs = forecaster().sim_outputs(n_sims=_n_sims(n_sims), seed=seed, perturbations=perturbations)
    return pd.DataFrame({t.team_id: t.reach_probs for t in outputs.teams}).T


def noise_floor(*, n_sims: int | None = None, seed: int = 0) -> float:
    """The paired-seed noise floor in pp: the largest per-team title move
    between two baselines that differ only by seed. Any cross-team delta
    below this floor is simulation noise, not signal."""
    a = baseline(n_sims=n_sims, seed=seed)
    b = baseline(n_sims=n_sims, seed=seed + 1)
    return round(max(abs(a[t] - b.get(t, 0.0)) for t in a) * 100, 3)


def impact(
    perturbation: Perturbation,
    *,
    n_sims: int | None = None,
    seed: int = 0,
    movers: int = 10,
    include_teams: list[str] | None = None,
) -> dict[str, Any]:
    """Per-team pp title deltas for one perturbation, with the paired-seed
    noise floor attached so sub-floor deltas read as the fiction they are."""
    included = _checked_tournament_teams(include_teams)
    base = baseline(n_sims=n_sims, seed=seed)
    moved = simulate((perturbation,), n_sims=n_sims, seed=seed)
    deltas = {t: round((moved.get(t, 0.0) - p) * 100, 3) for t, p in base.items()}
    top = dict(sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:movers])
    for team in included:
        top[team] = deltas[team]
    return {"deltas_pp": top, "noise_floor_pp": noise_floor(n_sims=n_sims, seed=seed)}


def match_probs(
    home: str,
    away: str,
    *,
    match: int | None = None,
    neutral: bool = True,
    perturbations: tuple[Perturbation, ...] | list[Perturbation] = (),
) -> dict[str, float]:
    """W/D/L for one fixture; pass the match id to bind match-keyed
    perturbations (without it they would be silently ignored, so the
    facade refuses instead)."""
    _checked_tournament_teams([home, away])
    perturbations = tuple(perturbations)
    _validate_quant_perturbations(perturbations)
    SESSION.usage.sims += 1
    return forecaster().match_probs(home, away, neutral=neutral, perturbations=perturbations, match=match)


def score_grid(
    home: str,
    away: str,
    *,
    match: int | None = None,
    neutral: bool = True,
    perturbations: tuple[Perturbation, ...] | list[Perturbation] = (),
) -> pd.DataFrame:
    """Full scoreline grid for one fixture as a DataFrame (rows home goals)."""
    import pandas as pd

    _checked_tournament_teams([home, away])
    perturbations = tuple(perturbations)
    _validate_quant_perturbations(perturbations)
    SESSION.usage.sims += 1
    grid = forecaster().score_grid(home, away, neutral=neutral, perturbations=perturbations, match=match)
    return pd.DataFrame(grid.grid)


def implied_delta(
    team: str,
    target_p: float,
    *,
    lo: float = -0.5,
    hi: float = 0.5,
    iterations: int = 12,
    n_sims: int | None = None,
    seed: int = 0,
) -> float:
    """Strength delta that moves the team's title probability to target_p:
    the translation of a model-vs-market gap into parameter units you can
    argue about (bisection, common random numbers)."""
    from wolves.forecast import StrengthPerturbation

    _checked_tournament_teams([team])
    for _ in range(iterations):
        mid = (lo + hi) / 2
        pert = StrengthPerturbation(team=team, delta=mid, reason="implied delta inversion")
        p = simulate((pert,), n_sims=n_sims, seed=seed)[team]
        lo, hi = (mid, hi) if p < target_p else (lo, mid)
    return round((lo + hi) / 2, 4)


def title_uncertainty(
    teams: list[str] | None = None,
    *,
    n_draws: int = 30,
    n_sims: int | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Title probability quantiles under the champion's own parameter
    uncertainty: strengths drawn from the MLE covariance, each draw
    re-simulated. A model-vs-market gap inside [p10, p90] is explainable as
    parameter noise; one outside it is structural disagreement."""
    import numpy as np
    import pandas as pd

    from wolves.forecast import StrengthPerturbation

    state = forecaster().state
    all_teams = list(state.teams)
    row_teams = _checked_tournament_teams(teams)
    draws = posterior_draws(n_draws, seed=seed)
    rows: dict[str, list[float]] = {t: [] for t in row_teams}
    for k in range(n_draws):
        perts = tuple(
            StrengthPerturbation(team=t, delta=float(draws.iloc[k][t] - state.strengths[i]), reason="posterior draw")
            for i, t in enumerate(all_teams)
            if abs(draws.iloc[k][t] - state.strengths[i]) > 1e-4
        )
        probs = simulate(perts, n_sims=n_sims, seed=seed)
        for t in rows:
            rows[t].append(probs[t])
    frame = pd.DataFrame(
        {
            "mean": {t: float(np.mean(v)) for t, v in rows.items()},
            "p10": {t: float(np.percentile(v, 10)) for t, v in rows.items()},
            "p50": {t: float(np.percentile(v, 50)) for t, v in rows.items()},
            "p90": {t: float(np.percentile(v, 90)) for t, v in rows.items()},
        }
    )
    frame.index.name = "team"
    return frame.sort_values("mean", ascending=False).reset_index().set_index("team", drop=False)


def update_from_result(
    team: str,
    opponent: str,
    outcome: str,
    *,
    team_at_home: bool = False,
    neutral: bool = True,
    match: int | None = None,
    grid_half_width: float = 0.4,
    points: int = 17,
) -> dict[str, float]:
    """Posterior strength-delta update justified by one observed result
    ("win", "draw" or "loss" for team): the model's own match likelihood over
    a delta grid, weighted by the champion's parameter prior. Calibrated
    expectation: even a shock loss justifies only ~|0.05|; expected results
    near zero. The qualification-path effect of the result flows separately
    through the simulator's played-results channel; never add it here."""
    import numpy as np

    from wolves.forecast import StrengthPerturbation

    _checked_tournament_teams([team, opponent])
    state = forecaster().state
    idx = list(state.teams).index(team)
    prior_sd = float(np.sqrt(state.covariance[idx, idx])) if state.covariance is not None else 0.12
    home, away = (team, opponent) if team_at_home else (opponent, team)
    key = {"win": "home" if team_at_home else "away", "loss": "away" if team_at_home else "home", "draw": "draw"}[
        outcome
    ]
    deltas = np.linspace(-grid_half_width, grid_half_width, points)
    likelihood = np.array(
        [
            forecaster().match_probs(
                home,
                away,
                neutral=neutral,
                match=match,
                perturbations=(StrengthPerturbation(team=team, delta=float(d), reason="result update"),),
            )[key]
            for d in deltas
        ]
    )
    SESSION.usage.sims += 1
    weights = np.exp(-0.5 * (deltas / prior_sd) ** 2) * likelihood
    weights /= weights.sum()
    mean = float(np.sum(weights * deltas))
    sd = float(np.sqrt(np.sum(weights * (deltas - mean) ** 2)))
    return {"posterior_mean_delta": round(mean, 4), "posterior_sd": round(sd, 4), "prior_sd": round(prior_sd, 4)}


def posterior_draws(n: int = 200, *, seed: int = 0) -> pd.DataFrame:
    """Per-team strength draws from the champion's MLE covariance, the free
    approximate posterior; columns are teams, one row per draw."""
    import numpy as np
    import pandas as pd

    state = forecaster().state
    if state.covariance is None:
        raise ValueError("the fitted state carries no covariance; refit with the full champion")
    mean = np.concatenate([state.strengths, [state.globals_["intercept"], state.globals_["home_adv"]]])
    rng = np.random.default_rng(seed)
    # svd tolerates the near-singular pinv covariance where cholesky would raise.
    draws = rng.multivariate_normal(mean, state.covariance, size=n, method="svd")
    SESSION.usage.sims += 1
    return pd.DataFrame(draws[:, : len(state.teams)], columns=list(state.teams))
