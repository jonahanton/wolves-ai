"""Model-driven match engine: rates from a fitted MatchModel state, parameter
uncertainty propagated by assigning each sim world one covariance draw, extra
time as a second Poisson draw at reduced intensity, shootouts exactly 50/50."""

from __future__ import annotations

import numpy as np

from wolves.data.teams import registry_team_key
from wolves.models.contracts import FittedState, UnknownModelTeamError
from wolves.sim.format import FormatData
from wolves.sim.venues import altitude_bonus_table, host_at_home_table

ET_INTENSITY = 1.0 / 3.0
PARAMETER_DRAWS = 200
# One Elo point on the log-rate strength axis, from regressing fitted strengths
# on current Elo ratings (10 Jun 2026); converts the altitude bonus between scales.
ALTITUDE_STRENGTH_PER_ELO = 0.0017


class PoissonMatchEngine:
    """Plugs a fitted one-strength Poisson state into the tournament MC."""

    def __init__(self, fmt: FormatData, state: FittedState, *, parameter_draws: int = PARAMETER_DRAWS) -> None:
        self._state = state
        self.parameter_draws = parameter_draws
        state_index = {team: i for i, team in enumerate(state.teams)}
        keys = [registry_team_key(team.id) for team in fmt.teams]
        for team, key in zip(fmt.teams, keys, strict=True):
            if key not in state_index:
                raise UnknownModelTeamError(team.id, state.model_id)
        self._param_idx = np.array([state_index[key] for key in keys], dtype=np.intp)

        self._at_home = host_at_home_table(fmt)
        self._altitude = altitude_bonus_table(fmt)
        self._strengths = np.empty(0)
        self._intercept = np.empty(0)
        self._home_adv = np.empty(0)
        self._sims = np.empty(0, dtype=np.intp)

    def begin(self, rng: np.random.Generator, n_sims: int) -> None:
        state = self._state
        mean = np.concatenate([state.strengths, [state.globals_["intercept"], state.globals_["home_adv"]]])
        n_params = mean.shape[0]
        if state.covariance is not None:
            # svd tolerates the near-singular pinv covariance where cholesky would raise.
            draws = rng.multivariate_normal(mean, state.covariance, size=self.parameter_draws, method="svd")
        else:
            draws = np.tile(mean, (self.parameter_draws, 1))
        world_draw = np.arange(n_sims) % self.parameter_draws
        params = draws[world_draw]
        self._strengths = params[:, : n_params - 2][:, self._param_idx].T
        self._intercept = params[:, n_params - 2]
        self._home_adv = params[:, n_params - 1]
        self._sims = np.arange(n_sims)

    def lambdas(self, home: np.ndarray, away: np.ndarray, *, city: str, stage: str) -> tuple[np.ndarray, np.ndarray]:
        s_home = self._strengths[home, self._sims]
        s_away = self._strengths[away, self._sims]
        adv = self._home_adv * self._at_home[city][home] + ALTITUDE_STRENGTH_PER_ELO * (
            self._altitude[city][home] - self._altitude[city][away]
        )
        diff = s_home - s_away + adv
        return np.exp(self._intercept + diff), np.exp(self._intercept - diff)

    def simulate_goals(
        self, rng: np.random.Generator, lam_home: np.ndarray, lam_away: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        return rng.poisson(lam_home), rng.poisson(lam_away)

    def knockout_home_wins(
        self, rng: np.random.Generator, home: np.ndarray, away: np.ndarray, hg: np.ndarray, ag: np.ndarray, *, city: str
    ) -> np.ndarray:
        lam_h, lam_a = self.lambdas(home, away, city=city, stage="knockout")
        et_home = rng.poisson(lam_h * ET_INTENSITY)
        et_away = rng.poisson(lam_a * ET_INTENSITY)
        shootout = rng.random(hg.shape[0]) < 0.5
        level_after_et = et_home == et_away
        level_winner = np.where(level_after_et, shootout, et_home > et_away)
        return np.where(hg == ag, level_winner, hg > ag)

    def record_result(
        self,
        home: np.ndarray,
        away: np.ndarray,
        hg: np.ndarray,
        ag: np.ndarray,
        home_wins: np.ndarray,
        *,
        city: str,
        stage: str,
    ) -> None:
        return None
