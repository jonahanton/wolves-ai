"""The deterministic engine behind one facade: fit, query, perturb, simulate.
The backend, the live loop and the agent tools import this and nothing deeper
(the gate and inverse simulation deliberately reach past it: they evaluate and
calibrate the parts the facade composes). Perturbations are typed and
quantified: every strength delta reports its output-space impact."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import numpy as np

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
)
from wolves.models.inmatch import MatchState, final_score_distribution, live_win_probabilities
from wolves.models.poisson import PoissonDecayModel, poisson_grid
from wolves.sim.api import SimOutputs
from wolves.sim.format import FormatData, PlayedResult, load_format, load_results
from wolves.sim.latent import LatentEffect
from wolves.sim.mc import MIN_GOAL_MEAN_AFTER_OFFSET, SimResult, run_tournament
from wolves.sim.model_engine import PoissonMatchEngine
from wolves.sim.outputs import build_focus_team, build_groups, build_matches, build_slots, build_team_reach
from wolves.sim.perturbations import (
    DeltaDistribution,
    HomeAdvantagePerturbation,
    MatchOutcomePerturbation,
    MatchRatePerturbation,
    Perturbation,
    ScorelinePerturbation,
    StateContext,
    StrengthPerturbation,
    TempoPerturbation,
    UnknownMatchError,
)
from wolves.sim.ratings import load_elo_ratings, load_squad_values
from wolves.snapshot import TeamInfo

DEFAULT_SIMS = 20_000

# Re-exported so existing imports (wq, agent, insights) keep their source of truth.
__all__ = [
    "DEFAULT_SIMS",
    "DeltaDistribution",
    "Forecaster",
    "HomeAdvantagePerturbation",
    "MatchOutcomePerturbation",
    "MatchRatePerturbation",
    "Perturbation",
    "ScorelinePerturbation",
    "StrengthPerturbation",
    "TempoPerturbation",
    "UnboundMatchPerturbationError",
    "UnknownMatchError",
]


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

    def restore(self, state: FittedState) -> None:
        """Adopt a previously fitted state, e.g. the published artifact."""
        self._state = state

    @property
    def is_fitted(self) -> bool:
        return self._state is not None

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
        """Apply every active perturbation through the registry protocol: each
        folds its parameter-space effect into the shared accumulators, then
        those needing the perturbed state (outcome reweights) build their grids.

        Mean shifts and covariance inflation land before the parameter draw;
        offsets and injected grids feed the per-fixture maths."""
        state = self.state
        active = [p for p in perturbations if p.active(on=state.as_of)]
        group_ids, knockout_ids = self._match_ids()

        ctx = StateContext(
            strengths=state.strengths.copy(),
            globals_=dict(state.globals_),
            extra_var=np.zeros(len(state.strengths) + 2),
            offsets={},
            grids={},
            team_index={team: i for i, team in enumerate(state.teams)},
            group_ids=frozenset(group_ids),
            knockout_ids=frozenset(knockout_ids),
            model=self.model,
            group_fixture_grid=lambda match, st: self.model.score_distribution(self._group_fixture(match), st),
            model_id=state.model_id,
        )
        # Parameter-space effects first, so the reweight reads the shifted state.
        for p in active:
            if not p.needs_perturbed_state:
                p.apply_to_state(ctx)
        perturbed = replace(state, strengths=ctx.strengths, globals_=ctx.globals_)
        ctx.perturbed_state = perturbed
        for p in active:
            if p.needs_perturbed_state:
                p.apply_to_state(ctx)
        return perturbed, ctx.offsets, ctx.grids, ctx.extra_var

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
        latent_effects: tuple[LatentEffect, ...] = (),
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
        in_match = tuple(p for p in perturbations if p.acts_in_match and p.active(on=state.as_of))
        engine = PoissonMatchEngine(self.fmt, state, latent_effects=latent_effects)
        return run_tournament(
            self.fmt,
            engine,
            n_sims=n_sims,
            seed=seed,
            results=results,
            fixture_goal_offsets=offsets or None,
            live_distributions=injected or None,
            in_match_perturbations=in_match,
        )

    def title_probs(
        self,
        *,
        n_sims: int = DEFAULT_SIMS,
        seed: int = 0,
        perturbations: tuple[Perturbation, ...] = (),
        latent_effects: tuple[LatentEffect, ...] = (),
        results: dict[int, PlayedResult] | None = None,
        live_distributions: dict[int, ScorelineDistribution] | None = None,
    ) -> dict[str, float]:
        result = self.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=perturbations,
            latent_effects=latent_effects,
            results=results,
            live_distributions=live_distributions,
            parameter_uncertainty=False,
        )
        winners = result.ko_winner[max(result.ko_winner)]
        return {team.id: float((winners == i).mean()) for i, team in enumerate(self.fmt.teams)}

    def played_results(self, *, extra_results: dict[int, PlayedResult] | None = None) -> dict[int, PlayedResult]:
        """Played results from the data directory, overlaid with freshly polled full times."""
        return load_results(self._settings.data_dir) | (extra_results or {})

    def sim_outputs(
        self,
        *,
        n_sims: int,
        seed: int = 0,
        perturbations: tuple[Perturbation, ...] = (),
        live_distributions: dict[int, ScorelineDistribution] | None = None,
        extra_results: dict[int, PlayedResult] | None = None,
        result: SimResult | None = None,
    ) -> SimOutputs:
        """Full snapshot outputs from the champion simulation, with played
        results baked in. A provided result skips the simulation; the caller
        guarantees it was simulated with the same played results."""
        results = self.played_results(extra_results=extra_results)
        if result is None:
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
