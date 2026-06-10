"""The deterministic engine behind one facade: fit, query, perturb, simulate.
The backend, the live loop and the agent tools import this and nothing deeper
(the gate and inverse simulation deliberately reach past it: they evaluate and
calibrate the parts the facade composes). Perturbations are typed and
quantified: every strength delta reports its output-space impact."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import numpy as np
from pydantic import BaseModel, Field, model_validator

from wolves.config import Settings
from wolves.data.contracts import MatchRecord
from wolves.data.overlay import overlay_results
from wolves.data.store import DatasetStore
from wolves.data.teams import registry_team_key
from wolves.gate.registry import ChampionRegistry
from wolves.models.contracts import (
    DatasetHandle,
    FittedState,
    Fixture,
    ScorelineDistribution,
    UnknownModelTeamError,
)
from wolves.models.inmatch import MatchState, final_score_distribution, live_win_probabilities
from wolves.models.poisson import PoissonDecayModel, poisson_grid
from wolves.sim.api import SimOutputs
from wolves.sim.format import FormatData, PlayedResult, load_format, load_results
from wolves.sim.mc import MIN_GOAL_MEAN_AFTER_OFFSET, SimResult, run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_focus_team, build_groups, build_matches, build_slots, build_team_reach
from wolves.sim.ratings import load_elo_ratings, load_squad_values
from wolves.snapshot import TeamInfo

DEFAULT_SIMS = 20_000


class _Perturbation(BaseModel):
    """Evidence-backed, typed and bounded; the harness quantifies every one in
    output space. Perturbations never carry tournament probabilities."""

    reason: str
    expires: date | None = None

    def active(self, *, on: date) -> bool:
        return self.expires is None or on <= self.expires


class DeltaDistribution(BaseModel):
    """A parameter delta whose magnitude is itself uncertain: Normal(mean, sd).

    The simulator integrates it by inflating the parameter covariance, so each
    sim world draws its own magnitude; fixture-level calls (score_grid,
    match_probs) price the mean only."""

    mean: float
    sd: float = Field(ge=0.0)


def _delta_mean(delta: float | DeltaDistribution) -> float:
    return delta.mean if isinstance(delta, DeltaDistribution) else delta


def _delta_var(delta: float | DeltaDistribution) -> float:
    return delta.sd**2 if isinstance(delta, DeltaDistribution) else 0.0


class StrengthPerturbation(_Perturbation):
    """Shift one team's ability, in strength units (log goal-rate scale).
    Calibration: top teams sit ~0.05 apart and 0.1 moves a favourite ~4pp of
    title probability; deltas beyond +/-0.3 imply a different team entirely."""

    team: str
    delta: float | DeltaDistribution


class TempoPerturbation(_Perturbation):
    """Shift the tournament-wide scoring intercept (log goals per side)."""

    delta: float | DeltaDistribution


class HomeAdvantagePerturbation(_Perturbation):
    """Shift the host home-advantage term."""

    delta: float | DeltaDistribution


class MatchRatePerturbation(_Perturbation):
    """Additive expected-goal offsets for one fixture (e.g. a tactical read)."""

    match: int
    home_goals_delta: float = 0.0
    away_goals_delta: float = 0.0


class MatchOutcomePerturbation(_Perturbation):
    """Reweight one group fixture's W/D/L mass; scorelines stay model-shaped
    within each outcome. Knockout pairings are sim-dependent, so this applies
    to group matches only."""

    match: int
    p_home: float
    p_draw: float
    p_away: float

    @model_validator(mode="after")
    def _probabilities_sum_to_one(self) -> MatchOutcomePerturbation:
        total = self.p_home + self.p_draw + self.p_away
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"outcome probabilities sum to {total:.3f}, not 1")
        return self


class ScorelinePerturbation(_Perturbation):
    """Pin one fixture to an exact scoreline (a what-if, not a forecast)."""

    match: int
    home_goals: int
    away_goals: int


Perturbation = (
    StrengthPerturbation
    | TempoPerturbation
    | HomeAdvantagePerturbation
    | MatchRatePerturbation
    | MatchOutcomePerturbation
    | ScorelinePerturbation
)


class UnknownMatchError(Exception):
    def __init__(self, match: int) -> None:
        self.match = match
        super().__init__(f"match {match} is not a fixture in the tournament format")


class UnboundMatchPerturbationError(Exception):
    """Match-keyed perturbations cannot bind to a fixture given only team
    names; refusing loudly beats silently pricing the unperturbed match."""

    def __init__(self, matches: list[int]) -> None:
        self.matches = matches
        super().__init__(
            f"perturbations are keyed to match(es) {matches}; pass match=<id> so they bind, "
            "or drop them from this fixture-level call"
        )


class Forecaster:
    """Fit once, then ask questions; every method is deterministic given a seed."""

    def __init__(self, settings: Settings, *, dataset: DatasetHandle | None = None) -> None:
        self._settings = settings
        self.fmt: FormatData = load_format(settings.data_dir)
        self.champion = ChampionRegistry(settings).load()
        self._dataset = dataset
        half_life = self.champion.half_life_days
        self.model = PoissonDecayModel(**({"half_life_days": half_life} if half_life else {}))
        self._state: FittedState | None = None

    @property
    def dataset(self) -> DatasetHandle:
        """Resolved lazily so champion-free paths never touch the dataset store."""
        if self._dataset is None:
            path, manifest = DatasetStore(self._settings).fetch()
            self._dataset = DatasetHandle(path=path, dataset_id=manifest.dataset_id)
        return self._dataset

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
            return self.fit()
        return self._state

    def _match_ids(self) -> tuple[set[int], set[int]]:
        group = {m.match for m in self.fmt.group_matches}
        knockout = {m.match for m in self.fmt.knockout}
        return group, knockout

    def _group_fixture(self, match: int) -> Fixture:
        spec = next(m for m in self.fmt.group_matches if m.match == match)
        return Fixture(home=registry_team_key(spec.home), away=registry_team_key(spec.away), neutral=True)

    def _perturbed(
        self, perturbations: tuple[Perturbation, ...]
    ) -> tuple[FittedState, dict[int, tuple[float, float]], dict[int, ScorelineDistribution], np.ndarray]:
        """Apply every active perturbation: parameter shifts land on the fitted
        state, fixture-level ones become goal offsets or injected distributions,
        and distribution-valued deltas accumulate per-parameter variance."""
        state = self.state
        active = [p for p in perturbations if p.active(on=state.as_of)]
        group_ids, knockout_ids = self._match_ids()

        strengths = state.strengths.copy()
        globals_ = dict(state.globals_)
        offsets: dict[int, tuple[float, float]] = {}
        extra_var = np.zeros(len(state.strengths) + 2)
        index = {team: i for i, team in enumerate(state.teams)}
        for p in active:
            if isinstance(p, StrengthPerturbation):
                key = registry_team_key(p.team)
                if key not in index:
                    raise UnknownModelTeamError(p.team, state.model_id)
                strengths[index[key]] += _delta_mean(p.delta)
                extra_var[index[key]] += _delta_var(p.delta)
            elif isinstance(p, TempoPerturbation):
                globals_["intercept"] += _delta_mean(p.delta)
                extra_var[-2] += _delta_var(p.delta)
            elif isinstance(p, HomeAdvantagePerturbation):
                globals_["home_adv"] += _delta_mean(p.delta)
                extra_var[-1] += _delta_var(p.delta)
            elif isinstance(p, MatchRatePerturbation):
                if p.match not in group_ids | knockout_ids:
                    raise UnknownMatchError(p.match)
                current = offsets.get(p.match, (0.0, 0.0))
                offsets[p.match] = (current[0] + p.home_goals_delta, current[1] + p.away_goals_delta)
        perturbed = replace(state, strengths=strengths, globals_=globals_)

        grids: dict[int, ScorelineDistribution] = {}
        for p in active:
            if isinstance(p, ScorelinePerturbation):
                if p.match not in group_ids | knockout_ids:
                    raise UnknownMatchError(p.match)
                grids[p.match] = ScorelineDistribution.single(p.home_goals, p.away_goals)
            elif isinstance(p, MatchOutcomePerturbation):
                # Knockout pairings vary per sim world, so only group fixtures reweight.
                if p.match not in group_ids:
                    raise UnknownMatchError(p.match)
                base = self.model.score_distribution(self._group_fixture(p.match), perturbed)
                grids[p.match] = base.reweighted(p_home=p.p_home, p_draw=p.p_draw, p_away=p.p_away)
        return perturbed, offsets, grids, extra_var

    def score_grid(
        self,
        home: str,
        away: str,
        *,
        neutral: bool = True,
        perturbations: tuple[Perturbation, ...] = (),
        match: int | None = None,
    ) -> ScorelineDistribution:
        """Scoreline grid for one fixture; match binds match-keyed perturbations."""
        fixture = Fixture(home=registry_team_key(home), away=registry_team_key(away), neutral=neutral)
        state, offsets, grids, _ = self._perturbed(perturbations)
        if match is None:
            keyed = sorted(set(offsets) | set(grids))
            if keyed:
                raise UnboundMatchPerturbationError(keyed)
            return self.model.score_distribution(fixture, state)
        if match in grids:
            return grids[match]
        lam_home, lam_away = self.model.rates(fixture, state)
        off_home, off_away = offsets.get(match, (0.0, 0.0))
        return poisson_grid(
            max(lam_home + off_home, MIN_GOAL_MEAN_AFTER_OFFSET),
            max(lam_away + off_away, MIN_GOAL_MEAN_AFTER_OFFSET),
            rho=state.globals_.get("rho", 0.0),
        )

    def match_probs(
        self,
        home: str,
        away: str,
        *,
        neutral: bool = True,
        perturbations: tuple[Perturbation, ...] = (),
        match: int | None = None,
    ) -> dict[str, float]:
        grid = self.score_grid(home, away, neutral=neutral, perturbations=perturbations, match=match)
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
        perturbations: tuple[Perturbation, ...] = (),
        results: dict[int, PlayedResult] | None = None,
        live_distributions: dict[int, ScorelineDistribution] | None = None,
        parameter_uncertainty: bool = True,
    ) -> SimResult:
        state, offsets, grids, extra_var = self._perturbed(perturbations)
        if not parameter_uncertainty:
            state = replace(state, covariance=None)
        if extra_var.any():
            # Injected magnitude uncertainty is the perturbation's own, so it
            # survives parameter_uncertainty=False; each sim world draws a magnitude.
            base_cov = state.covariance if state.covariance is not None else np.zeros((len(extra_var), len(extra_var)))
            state = replace(state, covariance=base_cov + np.diag(extra_var))
        # Live in-progress states outrank what-if injections for the same match.
        injected = {**grids, **(live_distributions or {})}
        engine = PoissonMatchEngine(self.fmt, state)
        return run_tournament(
            self.fmt,
            engine,
            n_sims=n_sims,
            seed=seed,
            results=results,
            fixture_goal_offsets=offsets or None,
            live_distributions=injected or None,
        )

    def title_probs(
        self,
        *,
        n_sims: int = DEFAULT_SIMS,
        seed: int = 0,
        perturbations: tuple[Perturbation, ...] = (),
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

    def sim_outputs(
        self,
        *,
        n_sims: int,
        seed: int = 0,
        perturbations: tuple[Perturbation, ...] = (),
        live_distributions: dict[int, ScorelineDistribution] | None = None,
        extra_results: dict[int, PlayedResult] | None = None,
    ) -> SimOutputs:
        """Full snapshot outputs from the champion simulation, with played
        results from the data directory baked in; extra_results overlay
        freshly polled full times."""
        results = load_results(self._settings.data_dir) | (extra_results or {})
        result = self.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=perturbations,
            results=results,
            live_distributions=live_distributions,
        )
        reach = build_team_reach(self.fmt, result)
        elo_path = sorted((self._settings.data_dir / "ratings").glob("elo-2*.tsv"))[-1]
        elo = load_elo_ratings(elo_path, self.fmt)
        values = load_squad_values(self._settings.data_dir / "ratings" / "squad-values.json", self.fmt)
        teams = [
            TeamInfo(
                team_id=team.id,
                name=team.name,
                group=team.group,
                elo=round(float(elo[i]), 1),
                rating=round(float(elo[i]), 1),
                value_eur_m=float(values[i]),
                champion_prob=reach[team.id]["champion"],
                reach_probs=reach[team.id],
            )
            for i, team in enumerate(self.fmt.teams)
        ]
        return SimOutputs(
            n_sims=n_sims,
            seed=seed,
            focus=build_focus_team(self.fmt, result, team_id=self._settings.focus_team),
            slots=build_slots(self.fmt, result),
            teams=teams,
            groups=build_groups(self.fmt, result),
            matches=build_matches(self.fmt, result, played=set(results)),
        )

    def perturbation_impact(
        self, perturbation: Perturbation, *, n_sims: int = DEFAULT_SIMS, seed: int = 0
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
            out[team.id] = (round(float(lo), 4), round(float(hi), 4))
        return out
