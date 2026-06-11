from __future__ import annotations

from typing import TYPE_CHECKING, Any

from wolves.forecast import Perturbation
from wolves.quant.wolves_quant._state import SESSION, context, forecaster

if TYPE_CHECKING:
    import pandas as pd


def _n_sims(n_sims: int | None) -> int:
    return n_sims or context().default_n_sims


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
    n_sims: int | None = None,
    seed: int = 0,
) -> dict[str, float]:
    """Title probabilities under perturbations, common random numbers by seed."""
    SESSION.usage.sims += 1
    return forecaster().title_probs(n_sims=_n_sims(n_sims), seed=seed, perturbations=tuple(perturbations))


def reach(
    perturbations: tuple[Perturbation, ...] | list[Perturbation] = (),
    *,
    n_sims: int | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Per-team reach probabilities through the rounds (rows teams, columns
    r32 to champion), common random numbers by seed."""
    import pandas as pd

    SESSION.usage.sims += 1
    outputs = forecaster().sim_outputs(n_sims=_n_sims(n_sims), seed=seed, perturbations=tuple(perturbations))
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
) -> dict[str, Any]:
    """Per-team pp title deltas for one perturbation, with the paired-seed
    noise floor attached so sub-floor deltas read as the fiction they are."""
    base = baseline(n_sims=n_sims, seed=seed)
    moved = simulate((perturbation,), n_sims=n_sims, seed=seed)
    deltas = {t: round((moved.get(t, 0.0) - p) * 100, 3) for t, p in base.items()}
    top = dict(sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:movers])
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
    SESSION.usage.sims += 1
    return forecaster().match_probs(home, away, neutral=neutral, perturbations=tuple(perturbations), match=match)


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

    SESSION.usage.sims += 1
    grid = forecaster().score_grid(home, away, neutral=neutral, perturbations=tuple(perturbations), match=match)
    return pd.DataFrame(grid.grid)


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
