"""The deterministic engine behind one facade: fit, query, perturb, simulate.
The backend, the live loop and the agent tools all import this and nothing
deeper. Perturbations are typed and quantified: every strength delta can
report its output-space impact before anyone acts on it."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import numpy as np
from pydantic import BaseModel

from wolves.config import Settings
from wolves.data.build import dataset_filename
from wolves.data.contracts import MatchRecord
from wolves.data.overlay import overlay_results
from wolves.data.teams import registry_team_key
from wolves.gate.registry import ChampionRegistry
from wolves.models.contracts import DatasetHandle, FittedState, Fixture, ScorelineDistribution
from wolves.models.inmatch import MatchState, final_score_distribution, live_win_probabilities
from wolves.models.poisson import PoissonDecayModel
from wolves.sim.format import FormatData, PlayedResult, load_format
from wolves.sim.mc import SimResult, run_tournament
from wolves.sim.model_engine import PoissonMatchEngine

DEFAULT_SIMS = 20_000


class StrengthPerturbation(BaseModel):
    """A bounded, evidence-backed shift to one team's ability, in strength
    units (log goal-rate scale). The harness quantifies it; it never carries
    probabilities."""

    team: str
    delta: float
    reason: str
    expires: date | None = None

    def active(self, *, on: date) -> bool:
        return self.expires is None or on <= self.expires


class Forecaster:
    """Fit once, then ask questions; every method is deterministic given a seed."""

    def __init__(self, settings: Settings, *, dataset: DatasetHandle | None = None) -> None:
        self._settings = settings
        self.fmt: FormatData = load_format(settings.data_dir)
        self.champion = ChampionRegistry(settings).load()
        self.dataset = dataset or DatasetHandle(
            path=settings.runs_root / "datasets" / dataset_filename(settings.dataset_version),
            version=settings.dataset_version,
        )
        half_life = self.champion.half_life_days
        self.model = PoissonDecayModel(**({"half_life_days": half_life} if half_life else {}))
        self._state: FittedState | None = None

    def fit(self, *, as_of: date | None = None, extra_results: list[MatchRecord] | None = None) -> FittedState:
        """Fit the champion; extra_results overlay fresh full-time results so a
        mid-tournament refit sees last night's games immediately."""
        dataset = self.dataset
        if extra_results:
            dataset = overlay_results(dataset, extra_results, dest_dir=self._settings.runs_root / "overlays")
        self._state = self.model.fit(dataset, as_of=as_of or datetime.now(UTC).date())
        return self._state

    @property
    def state(self) -> FittedState:
        if self._state is None:
            self.fit()
        assert self._state is not None
        return self._state

    def _perturbed(self, perturbations: tuple[StrengthPerturbation, ...]) -> FittedState:
        state = self.state
        active = [p for p in perturbations if p.active(on=state.as_of)]
        if not active:
            return state
        strengths = state.strengths.copy()
        index = {team: i for i, team in enumerate(state.teams)}
        for perturbation in active:
            strengths[index[registry_team_key(perturbation.team)]] += perturbation.delta
        return replace(state, strengths=strengths)

    def score_grid(
        self, home: str, away: str, *, neutral: bool = True, perturbations: tuple[StrengthPerturbation, ...] = ()
    ) -> ScorelineDistribution:
        fixture = Fixture(home=registry_team_key(home), away=registry_team_key(away), neutral=neutral)
        return self.model.score_distribution(fixture, self._perturbed(perturbations))

    def match_probs(
        self, home: str, away: str, *, neutral: bool = True, perturbations: tuple[StrengthPerturbation, ...] = ()
    ) -> dict[str, float]:
        grid = self.score_grid(home, away, neutral=neutral, perturbations=perturbations)
        return {"home": grid.p_home, "draw": grid.p_draw, "away": grid.p_away}

    def match_rates(self, home: str, away: str, *, neutral: bool = True) -> tuple[float, float]:
        fixture = Fixture(home=registry_team_key(home), away=registry_team_key(away), neutral=neutral)
        return self.model.rates(fixture, self.state)

    def live_match(self, home: str, away: str, state: MatchState, *, knockout: bool) -> dict[str, float]:
        lam_home, lam_away = self.match_rates(home, away)
        return live_win_probabilities(lam_home, lam_away, state, knockout=knockout)

    def live_distribution(self, home: str, away: str, state: MatchState) -> ScorelineDistribution:
        lam_home, lam_away = self.match_rates(home, away)
        return final_score_distribution(lam_home, lam_away, state)

    def simulate(
        self,
        *,
        n_sims: int = DEFAULT_SIMS,
        seed: int = 0,
        perturbations: tuple[StrengthPerturbation, ...] = (),
        results: dict[int, PlayedResult] | None = None,
        live_distributions: dict[int, ScorelineDistribution] | None = None,
        parameter_uncertainty: bool = True,
    ) -> SimResult:
        state = self._perturbed(perturbations)
        if not parameter_uncertainty:
            state = replace(state, covariance=None)
        engine = PoissonMatchEngine(self.fmt, state)
        return run_tournament(
            self.fmt, engine, n_sims=n_sims, seed=seed, results=results, live_distributions=live_distributions
        )

    def title_probs(
        self,
        *,
        n_sims: int = DEFAULT_SIMS,
        seed: int = 0,
        perturbations: tuple[StrengthPerturbation, ...] = (),
        results: dict[int, PlayedResult] | None = None,
        live_distributions: dict[int, ScorelineDistribution] | None = None,
    ) -> dict[str, float]:
        result = self.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=perturbations,
            results=results,
            live_distributions=live_distributions,
            parameter_uncertainty=False,
        )
        winners = result.ko_winner[max(result.ko_winner)]
        return {team.id: float((winners == i).mean()) for i, team in enumerate(self.fmt.teams)}

    def perturbation_impact(
        self, perturbation: StrengthPerturbation, *, n_sims: int = DEFAULT_SIMS, seed: int = 0
    ) -> dict[str, float]:
        """Output-space effect: percentage-point title-probability moves, the
        number every cap and every evidence ledger entry is denominated in."""
        before = self.title_probs(n_sims=n_sims, seed=seed)
        after = self.title_probs(n_sims=n_sims, seed=seed, perturbations=(perturbation,))
        deltas = {team: (after[team] - before[team]) * 100.0 for team in before}
        return {team: round(delta, 3) for team, delta in deltas.items() if abs(delta) > 0.05}

    def intervals(
        self, *, n_sims: int = 50_000, seed: int = 0, quantiles: tuple[float, float] = (0.1, 0.9)
    ) -> dict[str, tuple[float, float]]:
        """Title-probability intervals from parameter uncertainty: group sim
        worlds by covariance draw and take quantiles across draws."""
        engine = PoissonMatchEngine(self.fmt, self.state)
        result = run_tournament(self.fmt, engine, n_sims=n_sims, seed=seed)
        winners = result.ko_winner[max(result.ko_winner)]
        draws = np.arange(n_sims) % engine.parameter_draws
        out: dict[str, tuple[float, float]] = {}
        for i, team in enumerate(self.fmt.teams):
            won = winners == i
            per_draw = np.array([won[draws == d].mean() for d in range(engine.parameter_draws)])
            lo, hi = np.quantile(per_draw, quantiles)
            out[team.id] = (float(lo), float(hi))
        return out
