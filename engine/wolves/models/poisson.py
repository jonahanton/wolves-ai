"""Time-decayed weighted-MLE Poisson, one strength per team (an attack/defence
split scores worse for national teams), importance-weighted, home advantage
zeroed at neutral venues."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

import duckdb
import numpy as np
from scipy.optimize import minimize, minimize_scalar

from wolves.models.contracts import (
    MAX_GOALS,
    DatasetHandle,
    FittedState,
    Fixture,
    ScorelineDistribution,
    module_version,
)

logger = logging.getLogger(__name__)

MODEL_ID = "poisson-decay"
MODEL_VERSION = module_version(__file__)

DEFAULT_HALF_LIFE_DAYS = 913.0
# Beyond ~5 half-lives a match's weight is under 3%; older rows only slow the fit.
FIT_WINDOW_HALF_LIVES = 5.0
MIN_TEAM_MATCHES = 3
RIDGE = 1e-3
# Rates use only strength differences, so the mean must be pinned for identifiability.
MEAN_PENALTY = 10.0


@dataclass(frozen=True)
class _FitData:
    teams: tuple[str, ...]
    home_idx: np.ndarray
    away_idx: np.ndarray
    home_goals: np.ndarray
    away_goals: np.ndarray
    at_home: np.ndarray
    weights: np.ndarray
    dates: tuple[str, ...]
    tournaments: tuple[str, ...]
    importance: np.ndarray


class InsufficientFitDataError(Exception):
    def __init__(self, n_matches: int, as_of: date) -> None:
        self.n_matches = n_matches
        self.as_of = as_of
        super().__init__(f"only {n_matches} usable matches before {as_of}")


def load_fit_data(
    dataset: DatasetHandle, *, as_of: date, half_life_days: float, min_importance: float = 1.0
) -> _FitData:
    """Matches strictly before as_of, decay-weighted, restricted to teams with
    enough appearances to identify a strength."""
    window_start = as_of.toordinal() - half_life_days * FIT_WINDOW_HALF_LIVES
    connection = duckdb.connect(str(dataset.path), read_only=True)
    try:
        rows = connection.execute(
            "select date, home_team, away_team, home_goals, away_goals, importance, neutral, tournament"
            " from matches where date < ? and date >= ? and importance >= ? order by date",
            [as_of.isoformat(), date.fromordinal(int(window_start)).isoformat(), min_importance],
        ).fetchall()
    finally:
        connection.close()

    counts: dict[str, int] = {}
    for _, home, away, *_rest in rows:
        counts[home] = counts.get(home, 0) + 1
        counts[away] = counts.get(away, 0) + 1
    keep = {team for team, n in counts.items() if n >= MIN_TEAM_MATCHES}
    rows = [row for row in rows if row[1] in keep and row[2] in keep]
    if len(rows) < 500:
        raise InsufficientFitDataError(len(rows), as_of)

    teams = tuple(sorted(keep))
    index = {team: i for i, team in enumerate(teams)}
    played = np.array([row[0].toordinal() for row in rows], dtype=np.float64)
    decay = 0.5 ** ((as_of.toordinal() - played) / half_life_days)
    importance = np.array([row[5] for row in rows], dtype=np.float64)
    return _FitData(
        teams=teams,
        home_idx=np.array([index[row[1]] for row in rows], dtype=np.intp),
        away_idx=np.array([index[row[2]] for row in rows], dtype=np.intp),
        home_goals=np.array([row[3] for row in rows], dtype=np.float64),
        away_goals=np.array([row[4] for row in rows], dtype=np.float64),
        at_home=np.array([0.0 if row[6] else 1.0 for row in rows], dtype=np.float64),
        weights=decay * importance,
        dates=tuple(row[0].isoformat() for row in rows),
        tournaments=tuple(row[7] for row in rows),
        importance=importance,
    )


def _unpack(params: np.ndarray) -> tuple[np.ndarray, float, float]:
    return params[:-2], params[-2], params[-1]


def _neg_log_likelihood(
    params: np.ndarray, data: _FitData, prior_weight: np.ndarray | None = None, prior: np.ndarray | None = None
) -> tuple[float, np.ndarray]:
    strengths, intercept, home_adv = _unpack(params)
    diff = strengths[data.home_idx] - strengths[data.away_idx]
    lam_home = np.exp(intercept + diff + home_adv * data.at_home)
    lam_away = np.exp(intercept - diff)

    w = data.weights
    total = float(strengths.sum())
    nll = -float(np.sum(w * (data.home_goals * np.log(lam_home) - lam_home)))
    nll -= float(np.sum(w * (data.away_goals * np.log(lam_away) - lam_away)))
    nll += RIDGE * float(strengths @ strengths) + MEAN_PENALTY * total**2

    resid_home = w * (data.home_goals - lam_home)
    resid_away = w * (data.away_goals - lam_away)
    grad_strengths = np.zeros(strengths.shape[0])
    np.add.at(grad_strengths, data.home_idx, resid_home - resid_away)
    np.add.at(grad_strengths, data.away_idx, resid_away - resid_home)
    grad_strengths -= 2.0 * RIDGE * strengths + 2.0 * MEAN_PENALTY * total
    if prior_weight is not None and prior is not None:
        nll += float(np.sum(prior_weight * (strengths - prior) ** 2))
        grad_strengths -= 2.0 * prior_weight * (strengths - prior)
    grad_intercept = float(np.sum(resid_home + resid_away))
    grad_home_adv = float(np.sum(resid_home * data.at_home))
    return nll, -np.concatenate([grad_strengths, [grad_intercept, grad_home_adv]])


def _hessian(params: np.ndarray, data: _FitData, prior_weight: np.ndarray | None = None) -> np.ndarray:
    """Observed information of the weighted Poisson log-likelihood (exact for
    the log-linear rate; the ridge adds to the strength diagonal)."""
    strengths, intercept, home_adv = _unpack(params)
    diff = strengths[data.home_idx] - strengths[data.away_idx]
    lam_home = data.weights * np.exp(intercept + diff + home_adv * data.at_home)
    lam_away = data.weights * np.exp(intercept - diff)

    n_teams = strengths.shape[0]
    size = n_teams + 2
    hessian = np.zeros((size, size))
    both = lam_home + lam_away
    np.add.at(hessian, (data.home_idx, data.home_idx), both)
    np.add.at(hessian, (data.away_idx, data.away_idx), both)
    np.add.at(hessian, (data.home_idx, data.away_idx), -both)
    np.add.at(hessian, (data.away_idx, data.home_idx), -both)
    hessian[:n_teams, :n_teams] += 2.0 * RIDGE * np.eye(n_teams) + 2.0 * MEAN_PENALTY
    if prior_weight is not None:
        hessian[:n_teams, :n_teams] += 2.0 * np.diag(prior_weight)

    d_strength = np.zeros(n_teams)
    np.add.at(d_strength, data.home_idx, lam_home - lam_away)
    np.add.at(d_strength, data.away_idx, lam_away - lam_home)
    hessian[:n_teams, n_teams] = hessian[n_teams, :n_teams] = d_strength

    home_part = lam_home * data.at_home
    d_home = np.zeros(n_teams)
    np.add.at(d_home, data.home_idx, home_part)
    np.add.at(d_home, data.away_idx, -home_part)
    hessian[:n_teams, n_teams + 1] = hessian[n_teams + 1, :n_teams] = d_home

    hessian[n_teams, n_teams] = float(np.sum(both))
    hessian[n_teams, n_teams + 1] = hessian[n_teams + 1, n_teams] = float(np.sum(home_part))
    hessian[n_teams + 1, n_teams + 1] = float(np.sum(home_part))
    return hessian


def load_elo_covariate(dataset: DatasetHandle, *, as_of: date) -> dict[str, float]:
    """Load the year-end Elo snapshot preceding as_of."""
    connection = duckdb.connect(str(dataset.path), read_only=True)
    try:
        if "elo_history" not in {row[0] for row in connection.execute("show tables").fetchall()}:
            return {}
        rows = connection.execute(
            "select team, elo from elo_history where year = (select max(year) from elo_history where year < ?)",
            [as_of.year],
        ).fetchall()
    finally:
        connection.close()
    return {team: float(elo) for team, elo in rows}


def _elo_prior(strengths: np.ndarray, teams: tuple[str, ...], elo: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """Regress fitted strengths on Elo; return (has_elo mask, prior strengths)."""
    has_elo = np.array([team in elo for team in teams])
    values = np.array([elo.get(team, 0.0) for team in teams])
    design = np.column_stack([np.ones(int(has_elo.sum())), values[has_elo]])
    coef, *_ = np.linalg.lstsq(design, strengths[has_elo], rcond=None)
    return has_elo, coef[0] + coef[1] * values


def _fit_rho(data: _FitData, strengths: np.ndarray, intercept: float, home_adv: float) -> float:
    """Profile the Dixon-Coles low-score parameter with strengths held fixed."""
    diff = strengths[data.home_idx] - strengths[data.away_idx]
    lam_home = np.exp(intercept + diff + home_adv * data.at_home)
    lam_away = np.exp(intercept - diff)
    hg, ag, w = data.home_goals, data.away_goals, data.weights

    def neg_loglik(rho: float) -> float:
        tau = np.ones(hg.shape[0])
        tau = np.where((hg == 0) & (ag == 0), 1.0 - lam_home * lam_away * rho, tau)
        tau = np.where((hg == 0) & (ag == 1), 1.0 + lam_home * rho, tau)
        tau = np.where((hg == 1) & (ag == 0), 1.0 + lam_away * rho, tau)
        tau = np.where((hg == 1) & (ag == 1), 1.0 - rho, tau)
        return -float(np.sum(w * np.log(np.clip(tau, 1e-9, None))))

    result = minimize_scalar(neg_loglik, bounds=(-0.25, 0.25), method="bounded")
    return float(result.x)


class PoissonDecayModel:
    """Time-decayed one-strength Poisson behind the MatchModel contract, with
    optional Dixon-Coles low-score correction and Elo shrinkage prior."""

    model_id = MODEL_ID
    version = MODEL_VERSION

    def __init__(
        self,
        *,
        half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
        dixon_coles: bool = False,
        elo_prior_weight: float = 0.0,
        min_importance: float = 1.0,
    ) -> None:
        self.half_life_days = half_life_days
        self.dixon_coles = dixon_coles
        self.elo_prior_weight = elo_prior_weight
        self.min_importance = min_importance

    def fit(self, dataset: DatasetHandle, *, as_of: date, seed: int = 0) -> FittedState:
        data = load_fit_data(
            dataset, as_of=as_of, half_life_days=self.half_life_days, min_importance=self.min_importance
        )
        n_teams = len(data.teams)
        start = np.zeros(n_teams + 2)
        start[-2] = math.log(1.3)
        result = minimize(
            _neg_log_likelihood, start, args=(data,), jac=True, method="L-BFGS-B", options={"maxiter": 2000}
        )
        if not result.success:
            logger.warning("poisson fit did not converge cleanly: %s", result.message)

        prior_weight = None
        if self.elo_prior_weight > 0.0:
            elo = load_elo_covariate(dataset, as_of=as_of)
            if elo:
                strengths, *_ = _unpack(result.x)
                has_elo, prior = _elo_prior(strengths, data.teams, elo)
                prior_weight = has_elo * self.elo_prior_weight
                result = minimize(
                    _neg_log_likelihood,
                    result.x,
                    args=(data, prior_weight, prior),
                    jac=True,
                    method="L-BFGS-B",
                    options={"maxiter": 2000},
                )

        covariance = np.linalg.pinv(_hessian(result.x, data, prior_weight))
        strengths, intercept, home_adv = _unpack(result.x)
        rho = _fit_rho(data, strengths, intercept, home_adv) if self.dixon_coles else 0.0
        return FittedState(
            model_id=self.model_id,
            version=self.version,
            dataset_id=dataset.dataset_id,
            as_of=as_of,
            teams=data.teams,
            strengths=strengths,
            globals_={
                "intercept": float(intercept),
                "home_adv": float(home_adv),
                "half_life_days": self.half_life_days,
                "rho": rho,
                "elo_prior_weight": self.elo_prior_weight,
            },
            covariance=covariance,
            diagnostics={"n_matches": float(data.weights.shape[0]), "nll": float(result.fun)},
        )

    def rates(self, fixture: Fixture, state: FittedState) -> tuple[float, float]:
        diff = state.strength_of(fixture.home) - state.strength_of(fixture.away)
        intercept = state.globals_["intercept"]
        home_adv = 0.0 if fixture.neutral else state.globals_["home_adv"]
        return math.exp(intercept + diff + home_adv), math.exp(intercept - diff)

    def score_distribution(
        self, fixture: Fixture, state: FittedState, *, intensity: float = 1.0
    ) -> ScorelineDistribution:
        lam_home, lam_away = self.rates(fixture, state)
        return poisson_grid(lam_home * intensity, lam_away * intensity, rho=state.globals_.get("rho", 0.0))


def poisson_grid(lam_home: float, lam_away: float, *, rho: float = 0.0) -> ScorelineDistribution:
    goals = np.arange(MAX_GOALS + 1)
    log_fact = np.cumsum(np.concatenate([[0.0], np.log(goals[1:])]))
    p_home = np.exp(goals * math.log(lam_home) - lam_home - log_fact)
    p_away = np.exp(goals * math.log(lam_away) - lam_away - log_fact)
    grid = np.outer(p_home, p_away)
    if rho != 0.0:
        grid[0, 0] *= max(1.0 - lam_home * lam_away * rho, 1e-9)
        grid[0, 1] *= max(1.0 + lam_home * rho, 1e-9)
        grid[1, 0] *= max(1.0 + lam_away * rho, 1e-9)
        grid[1, 1] *= max(1.0 - rho, 1e-9)
    return ScorelineDistribution(grid=grid / grid.sum())
