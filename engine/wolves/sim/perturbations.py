"""The perturbation vocabulary as a plug-and-play registry.

A perturbation is a typed belief the engine integrates, never a tournament
probability vector. Each type carries its own apply-logic behind two hooks so
the engine never switches on type: apply_to_state folds a parameter-space effect
into the pre-draw accumulators; apply_in_match adjusts per-sim lambdas for
effects conditional on a pairing only some sims realise. Adding a type is one
model class plus one PERTURBATIONS entry; the union, the wq exports and the
artifact parser all walk the registry, and publishes=False gates what-ifs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from wolves.data.teams import canonical_team_key, registry_team_key
from wolves.models.contracts import ScorelineDistribution

if TYPE_CHECKING:
    from wolves.models.contracts import FittedState
    from wolves.models.poisson import PoissonDecayModel


class DeltaDistribution(BaseModel):
    """A parameter delta whose magnitude is itself uncertain: Normal(mean, sd).

    The simulator integrates it by inflating the parameter covariance, so each
    sim world draws its own magnitude; fixture-level calls price the mean only.
    sd is effect-size uncertainty given the world, never a generic band-widener:
    the fitted covariance already owns baseline-strength uncertainty, and sd
    re-adding it would double-count in the same space."""

    mean: float
    sd: float = Field(ge=0.0)


KnockoutStage = Literal["r32", "r16", "qf", "sf", "final"]


def delta_mean(delta: float | DeltaDistribution) -> float:
    return delta.mean if isinstance(delta, DeltaDistribution) else delta


def delta_var(delta: float | DeltaDistribution) -> float:
    return delta.sd**2 if isinstance(delta, DeltaDistribution) else 0.0


class UnknownMatchError(Exception):
    def __init__(self, match: int) -> None:
        self.match = match
        super().__init__(f"match {match} is not a fixture in the tournament format")


@dataclass
class StateContext:
    """The pre-draw accumulators a parameter-space perturbation folds into."""

    strengths: np.ndarray
    globals_: dict[str, float]
    extra_var: np.ndarray
    offsets: dict[int, tuple[float, float]]
    grids: dict[int, ScorelineDistribution]
    team_index: dict[str, int]
    group_ids: frozenset[int]
    knockout_ids: frozenset[int]
    model: PoissonDecayModel
    group_fixture_grid: object  # Callable[[int, FittedState], ScorelineDistribution]
    model_id: str = ""
    perturbed_state: FittedState | None = None

    def require_match(self, match: int) -> None:
        if match not in self.group_ids | self.knockout_ids:
            raise UnknownMatchError(match)


class _Perturbation(BaseModel):
    """Evidence-backed, typed and bounded; the harness quantifies every one in
    output space. Perturbations never carry tournament probabilities."""

    name: ClassVar[str]
    # apply_to_state reads the post-shift state, so the driver runs it second.
    needs_perturbed_state: ClassVar[bool] = False
    # the effect is conditional on a per-sim pairing, applied inside the loop.
    acts_in_match: ClassVar[bool] = False
    # the effect reweights the resolved knockout advance, after the tie is decided.
    acts_on_outcome: ClassVar[bool] = False

    reason: str
    expires: date | None = None

    def active(self, *, on: date) -> bool:
        return self.expires is None or on <= self.expires

    def apply_to_state(self, ctx: StateContext) -> None:
        """Fold a parameter-space effect into the pre-draw accumulators."""

    def apply_in_match(self, mctx: MatchContext) -> None:
        """Adjust per-match lambdas in place on the sims its condition matches."""

    def resolve_outcome(self, kctx: KnockoutContext) -> None:
        """Reweight the resolved knockout advance on the sims its pairing matches."""


class StrengthPerturbation(_Perturbation):
    """Shift one team's ability, in strength units (log goal-rate scale).
    Calibration: top teams sit ~0.05 apart and 0.1 moves a favourite ~4pp of
    title probability; deltas beyond +/-0.3 imply a different team entirely."""

    name: ClassVar[str] = "strength"
    type: Literal["strength"] = "strength"

    team: str
    delta: float | DeltaDistribution

    @field_validator("team")
    @classmethod
    def _canonical(cls, value: str) -> str:
        # Internal tables join on the canonical slug, not the display case.
        return canonical_team_key(value)

    def apply_to_state(self, ctx: StateContext) -> None:
        from wolves.models.contracts import UnknownModelTeamError

        key = registry_team_key(self.team)
        if key not in ctx.team_index:
            raise UnknownModelTeamError(self.team, ctx.model_id)
        i = ctx.team_index[key]
        ctx.strengths[i] += delta_mean(self.delta)
        ctx.extra_var[i] += delta_var(self.delta)


class TempoPerturbation(_Perturbation):
    """Shift the tournament-wide scoring intercept (log goals per side)."""

    name: ClassVar[str] = "tempo"
    type: Literal["tempo"] = "tempo"

    delta: float | DeltaDistribution

    def apply_to_state(self, ctx: StateContext) -> None:
        ctx.globals_["intercept"] += delta_mean(self.delta)
        ctx.extra_var[-2] += delta_var(self.delta)


class HomeAdvantagePerturbation(_Perturbation):
    """Shift the host home-advantage term."""

    name: ClassVar[str] = "home_advantage"
    type: Literal["home_advantage"] = "home_advantage"

    delta: float | DeltaDistribution

    def apply_to_state(self, ctx: StateContext) -> None:
        ctx.globals_["home_adv"] += delta_mean(self.delta)
        ctx.extra_var[-1] += delta_var(self.delta)


class MatchRatePerturbation(_Perturbation):
    """Additive expected-goal offsets for one fixture (e.g. a tactical read)."""

    name: ClassVar[str] = "match_rate"
    type: Literal["match_rate"] = "match_rate"

    match: int
    home_goals_delta: float = 0.0
    away_goals_delta: float = 0.0

    def apply_to_state(self, ctx: StateContext) -> None:
        ctx.require_match(self.match)
        current = ctx.offsets.get(self.match, (0.0, 0.0))
        ctx.offsets[self.match] = (current[0] + self.home_goals_delta, current[1] + self.away_goals_delta)


class MatchOutcomePerturbation(_Perturbation):
    """Reweight one group fixture's W/D/L mass; scorelines stay model-shaped
    within each outcome. Knockout pairings are sim-dependent, so this applies
    to group matches only."""

    name: ClassVar[str] = "match_outcome"
    needs_perturbed_state: ClassVar[bool] = True
    type: Literal["match_outcome"] = "match_outcome"

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

    def apply_to_state(self, ctx: StateContext) -> None:
        if self.match not in ctx.group_ids:
            raise UnknownMatchError(self.match)
        assert ctx.perturbed_state is not None
        base = ctx.group_fixture_grid(self.match, ctx.perturbed_state)
        ctx.grids[self.match] = base.reweighted(p_home=self.p_home, p_draw=self.p_draw, p_away=self.p_away)


class ScorelinePerturbation(_Perturbation):
    """Pin one fixture to an exact scoreline (a what-if, not a forecast)."""

    name: ClassVar[str] = "scoreline"
    type: Literal["scoreline"] = "scoreline"

    match: int
    home_goals: int
    away_goals: int

    def apply_to_state(self, ctx: StateContext) -> None:
        ctx.require_match(self.match)
        ctx.grids[self.match] = ScorelineDistribution.single(self.home_goals, self.away_goals)


class OpponentConditionalStrength(_Perturbation):
    """Shift a team's ability only against named opponents (a matchup read, e.g.
    a side that struggles against a low block). Mirrors a strength shift on the
    sims where the pairing occurs: the team's goal rate scales by exp(delta) and
    the opponent's by exp(-delta), exactly as a whole-tournament shift would."""

    name: ClassVar[str] = "opponent_conditional_strength"
    acts_in_match: ClassVar[bool] = True
    type: Literal["opponent_conditional_strength"] = "opponent_conditional_strength"

    team: str
    opponents: list[str] = Field(min_length=1)
    delta: float

    @field_validator("team")
    @classmethod
    def _canonical_team(cls, value: str) -> str:
        return canonical_team_key(value)

    @field_validator("opponents")
    @classmethod
    def _canonical_opponents(cls, value: list[str]) -> list[str]:
        return [canonical_team_key(v) for v in value]

    def apply_in_match(self, mctx: MatchContext) -> None:
        team_col = mctx.column(self.team)
        opp_cols = [c for c in (mctx.column(o) for o in self.opponents) if c is not None]
        if team_col is None or not opp_cols:
            return
        against = np.isin(mctx.away, opp_cols)
        as_home = (mctx.home == team_col) & against
        against_home = np.isin(mctx.home, opp_cols)
        as_away = (mctx.away == team_col) & against_home
        scale = float(np.exp(self.delta))
        mctx.lam_home[as_home] *= scale
        mctx.lam_away[as_home] /= scale
        mctx.lam_away[as_away] *= scale
        mctx.lam_home[as_away] /= scale


class StageConditionalStrength(_Perturbation):
    """Shift a team's ability only in a given knockout round (e.g. a squad that
    raises its level once the tournament turns to elimination football)."""

    name: ClassVar[str] = "stage_conditional_strength"
    acts_in_match: ClassVar[bool] = True
    type: Literal["stage_conditional_strength"] = "stage_conditional_strength"

    team: str
    stage: KnockoutStage
    delta: float

    @field_validator("team")
    @classmethod
    def _canonical(cls, value: str) -> str:
        return canonical_team_key(value)

    def apply_in_match(self, mctx: MatchContext) -> None:
        if mctx.stage != self.stage:
            return
        team_col = mctx.column(self.team)
        if team_col is None:
            return
        scale = float(np.exp(self.delta))
        as_home = mctx.home == team_col
        as_away = mctx.away == team_col
        mctx.lam_home[as_home] *= scale
        mctx.lam_away[as_home] /= scale
        mctx.lam_away[as_away] *= scale
        mctx.lam_home[as_away] /= scale


class KnockoutOutcome(_Perturbation):
    """Bet on one team beating another should they meet in the knockouts, at a
    stated advance probability. Keyed on the pairing, not a fixture number,
    because a knockout matchup exists only in some sims; reweights the resolved
    advance whenever the pairing occurs (at the given stage, if set)."""

    name: ClassVar[str] = "knockout_outcome"
    acts_on_outcome: ClassVar[bool] = True
    type: Literal["knockout_outcome"] = "knockout_outcome"

    team: str
    opponent: str
    p_advance: float = Field(ge=0.0, le=1.0)
    stage: KnockoutStage | None = None

    @field_validator("team", "opponent")
    @classmethod
    def _canonical(cls, value: str) -> str:
        return canonical_team_key(value)

    @model_validator(mode="after")
    def _distinct(self) -> KnockoutOutcome:
        if self.team == self.opponent:
            raise ValueError("a knockout outcome needs two distinct teams")
        return self

    def resolve_outcome(self, kctx: KnockoutContext) -> None:
        if self.stage is not None and kctx.stage != self.stage:
            return
        team_col = kctx.column(self.team)
        opp_col = kctx.column(self.opponent)
        if team_col is None or opp_col is None:
            return
        team_home = (kctx.home == team_col) & (kctx.away == opp_col)
        team_away = (kctx.home == opp_col) & (kctx.away == team_col)
        matched = team_home | team_away
        if not matched.any():
            return
        team_advances = kctx.rng.random(kctx.home.shape[0]) < self.p_advance
        kctx.home_wins[matched] = np.where(team_home, team_advances, ~team_advances)[matched]


@dataclass
class MatchContext:
    """Per-match state an in-match perturbation adjusts: per-sim team arrays and
    the per-sim lambdas it may shift on the sims its condition matches. stage is
    the fine round (r32..final for knockouts, "group" otherwise)."""

    home: np.ndarray
    away: np.ndarray
    city: str
    stage: str
    match: int
    lam_home: np.ndarray
    lam_away: np.ndarray
    team_index: dict[str, int]

    def column(self, team: str) -> int | None:
        return self.team_index.get(registry_team_key(team))


@dataclass
class KnockoutContext:
    """A resolved knockout tie an outcome perturbation may reweight: per-sim
    home/away team arrays, the decided home_wins mask, the stage and the rng for
    the reweight draw. home_wins is mutated in place on the matching sims."""

    home: np.ndarray
    away: np.ndarray
    home_wins: np.ndarray
    stage: str
    rng: np.random.Generator
    team_index: dict[str, int]

    def column(self, team: str) -> int | None:
        return self.team_index.get(registry_team_key(team))


@dataclass(frozen=True)
class PerturbationSpec:
    """One registry entry: the model class, whether it publishes, and its scope."""

    model: type[_Perturbation]
    publishes: bool
    scope: str = "tournament"

    @property
    def name(self) -> str:
        return self.model.name


PERTURBATIONS: tuple[PerturbationSpec, ...] = (
    PerturbationSpec(StrengthPerturbation, publishes=True),
    PerturbationSpec(TempoPerturbation, publishes=True),
    PerturbationSpec(HomeAdvantagePerturbation, publishes=True),
    PerturbationSpec(MatchRatePerturbation, publishes=True, scope="fixture"),
    PerturbationSpec(MatchOutcomePerturbation, publishes=True, scope="group_fixture"),
    PerturbationSpec(ScorelinePerturbation, publishes=False, scope="fixture"),
    PerturbationSpec(OpponentConditionalStrength, publishes=True, scope="conditional"),
    PerturbationSpec(StageConditionalStrength, publishes=True, scope="conditional"),
    PerturbationSpec(KnockoutOutcome, publishes=True, scope="knockout_pairing"),
)

_BY_NAME: dict[str, PerturbationSpec] = {spec.name: spec for spec in PERTURBATIONS}


def spec_for(perturbation: _Perturbation) -> PerturbationSpec:
    return _BY_NAME[type(perturbation).name]


def _union() -> object:
    # Plain, not discriminated: artifacts predating the type tag omit it and
    # must still parse; the tag only disambiguates tempo from home_advantage.
    models = tuple(spec.model for spec in PERTURBATIONS)
    union = models[0]
    for model in models[1:]:
        union = union | model
    return union


Perturbation = _union()
_ADAPTER: TypeAdapter = TypeAdapter(Perturbation)


def parse_perturbation(payload: dict) -> _Perturbation:
    return _ADAPTER.validate_python(payload)
