"""Sidecar datasets published beside a snapshot: payload models, producers and the registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable

    from wolves.sim.format import FormatData
    from wolves.sim.mc import SimResult

KO_ROUNDS = ("r32", "r16", "qf", "sf", "final")
DEFAULT_BRACKET_SAMPLES = 100
TOP_OPPONENTS = 8


class UnknownSidecarError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"no sidecar dataset named {name!r}")


@dataclass(frozen=True)
class SidecarInputs:
    """What publish time has in hand; played holds match numbers with a final
    result, which producers skip wherever per-sim variation is required."""

    fmt: FormatData
    per_world_results: dict[str, SimResult]
    weights: dict[str, float]
    parameter_draws: int
    rng_seed: int
    played: frozenset[int] = frozenset()


class BracketSampleMatch(BaseModel):
    match: int
    stage: str
    home: str
    away: str
    winner: str


class BracketSample(BaseModel):
    world: str
    matches: list[BracketSampleMatch]


class BracketSamples(BaseModel):
    samples: list[BracketSample]


class OpponentProb(BaseModel):
    opponent: str
    p: float


class PairingMatrices(BaseModel):
    rounds: dict[str, dict[str, list[OpponentProb]]]


class MatchWdl(BaseModel):
    p_home: list[float]
    p_draw: list[float]
    p_away: list[float]


class MatchWdlDraws(BaseModel):
    matches: dict[int, MatchWdl]


class CellShape(BaseModel):
    """Histogram and per-world components for one open team-stage cell."""

    bin_edges: list[float]
    histogram: list[float]
    world_bins: dict[str, list[float]]
    components: dict[str, dict[str, float]]


class DistributionsSidecar(BaseModel):
    quantile_levels: list[float]
    provenance: str
    teams: dict[str, dict[str, CellShape]]


def build_bracket_samples(inputs: SidecarInputs, *, n_samples: int = DEFAULT_BRACKET_SAMPLES) -> BracketSamples:
    """Sample full bracket realisations: a world by weight, then a uniform sim within it."""
    rng = np.random.default_rng(inputs.rng_seed)
    names = list(inputs.weights)
    probs = np.array([inputs.weights[name] for name in names], dtype=np.float64)
    chosen = rng.choice(len(names), size=n_samples, p=probs / probs.sum())
    matches = sorted(inputs.fmt.knockout, key=lambda m: m.match)
    teams = inputs.fmt.teams
    # Samples keep the random draw order, so any first-N slice is unbiased.
    per_world: dict[int, list[BracketSample]] = {}
    for w_i, name in enumerate(names):
        result = inputs.per_world_results[name]
        sims = rng.integers(result.n_sims, size=int((chosen == w_i).sum()))
        columns = {
            m.match: (result.ko_home[m.match][sims], result.ko_away[m.match][sims], result.ko_winner[m.match][sims])
            for m in matches
        }
        per_world[w_i] = [
            BracketSample(
                world=name,
                matches=[
                    BracketSampleMatch(
                        match=m.match,
                        stage=m.stage,
                        home=teams[int(columns[m.match][0][k])].id,
                        away=teams[int(columns[m.match][1][k])].id,
                        winner=teams[int(columns[m.match][2][k])].id,
                    )
                    for m in matches
                ],
            )
            for k in range(sims.size)
        ]
    return BracketSamples(samples=[per_world[w_i].pop(0) for w_i in chosen])


def build_pairing_matrices(inputs: SidecarInputs) -> PairingMatrices:
    """P(team A meets team B in round R), counted across sims and mixed over worlds by weight."""
    fmt = inputs.fmt
    n_teams = len(fmt.teams)
    rounds: dict[str, dict[str, list[OpponentProb]]] = {}
    for rnd in KO_ROUNDS:
        meet = np.zeros((n_teams, n_teams))
        for name, weight in inputs.weights.items():
            result = inputs.per_world_results[name]
            for m in fmt.knockout:
                if m.stage != rnd:
                    continue
                np.add.at(meet, (result.ko_home[m.match], result.ko_away[m.match]), weight / result.n_sims)
        meet = meet + meet.T
        per_team: dict[str, list[OpponentProb]] = {}
        for i, team in enumerate(fmt.teams):
            top = np.argsort(meet[i])[::-1][:TOP_OPPONENTS]
            per_team[team.id] = [
                OpponentProb(opponent=fmt.teams[int(j)].id, p=round(float(meet[i, j]), 4))
                for j in top
                if meet[i, j] > 0
            ]
        rounds[rnd] = per_team
    return PairingMatrices(rounds=rounds)


def build_match_wdl_draws(inputs: SidecarInputs) -> MatchWdlDraws:
    """Per-parameter-draw W/D/L for group matches, mixed over worlds by weight.

    Sims map to draws by i % parameter_draws, mirroring the model engine's
    world assignment. Matches in inputs.played are skipped: their goals are
    fixed, so a per-draw spread would be meaningless."""
    n_draws = inputs.parameter_draws
    out: dict[int, MatchWdl] = {}
    for m in inputs.fmt.group_matches:
        if m.match in inputs.played:
            continue
        p_home = np.zeros(n_draws)
        p_draw = np.zeros(n_draws)
        p_away = np.zeros(n_draws)
        for name, weight in inputs.weights.items():
            result = inputs.per_world_results[name]
            hg, ag = result.group_goals[m.match]
            draw_idx = np.arange(result.n_sims) % n_draws
            counts = np.maximum(np.bincount(draw_idx, minlength=n_draws), 1)
            p_home += weight * np.bincount(draw_idx, weights=hg > ag, minlength=n_draws) / counts
            p_draw += weight * np.bincount(draw_idx, weights=hg == ag, minlength=n_draws) / counts
            p_away += weight * np.bincount(draw_idx, weights=hg < ag, minlength=n_draws) / counts
        out[m.match] = MatchWdl(
            p_home=[round(float(p), 4) for p in p_home],
            p_draw=[round(float(p), 4) for p in p_draw],
            p_away=[round(float(p), 4) for p in p_away],
        )
    return MatchWdlDraws(matches=out)


@dataclass(frozen=True)
class SidecarDataset:
    """produce is None for datasets whose payload the publish path assembles
    itself (distributions shares one pass with the snapshot block); the entry
    still registers the name and wire model for the publisher and the API."""

    name: str
    model: type[BaseModel]
    produce: Callable[[SidecarInputs], BaseModel] | None


SIDECARS: tuple[SidecarDataset, ...] = (
    SidecarDataset(name="distributions", model=DistributionsSidecar, produce=None),
    SidecarDataset(name="bracket-samples", model=BracketSamples, produce=build_bracket_samples),
    SidecarDataset(name="pairing-matrices", model=PairingMatrices, produce=build_pairing_matrices),
    SidecarDataset(name="match-wdl-draws", model=MatchWdlDraws, produce=build_match_wdl_draws),
)

SIDECAR_NAMES = frozenset(spec.name for spec in SIDECARS)


def sidecar_dataset(name: str) -> SidecarDataset:
    for spec in SIDECARS:
        if spec.name == name:
            return spec
    raise UnknownSidecarError(name)
