from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from wolves.config import get_settings
from wolves.sim.engine import EloMatchEngine
from wolves.sim.format import PlayedResult, load_format, load_results
from wolves.sim.mc import run_tournament
from wolves.sim.outputs import build_focus_team, build_groups, build_matches, build_slots, build_team_reach
from wolves.sim.ratings import blend_value_prior, load_elo_ratings, load_squad_values
from wolves.snapshot import FocusTeamBlock, GroupBlock, MatchProbs, Slot, TeamInfo


class UnknownTeamError(Exception):
    def __init__(self, team_id: str) -> None:
        self.team_id = team_id
        super().__init__(f"unknown team id {team_id!r} in rating overrides")


class SimInputs(BaseModel):
    """Inputs to run_simulation; rating overrides are additive Elo deltas by team id."""

    rating_overrides: dict[str, float] = Field(default_factory=dict)
    fixture_goal_offsets: dict[int, tuple[float, float]] = Field(default_factory=dict)
    n_sims: int = 100_000
    seed: int | None = None


class SimOutputs(BaseModel):
    n_sims: int
    seed: int
    focus: FocusTeamBlock
    slots: list[Slot]
    teams: list[TeamInfo]
    groups: list[GroupBlock]
    matches: list[MatchProbs]


def run_simulation(
    rating_overrides: dict[str, float],
    fixture_goal_offsets: dict[int, tuple[float, float]],
    n_sims: int,
    seed: int | None,
    *,
    extra_results: dict[int, PlayedResult] | None = None,
) -> SimOutputs:
    """Run the full tournament simulation; the frozen interface the agent harness calls.

    extra_results are polled live results overlaid on top of the results file."""
    inputs = SimInputs(
        rating_overrides=rating_overrides,
        fixture_goal_offsets=fixture_goal_offsets,
        n_sims=n_sims,
        seed=seed,
    )
    settings = get_settings()
    data_dir = settings.data_dir
    fmt = load_format(data_dir)
    results = load_results(data_dir) | (extra_results or {})

    elo_path = sorted((data_dir / "ratings").glob("elo-2*.tsv"))[-1]
    elo = load_elo_ratings(elo_path, fmt)
    values = load_squad_values(data_dir / "ratings" / "squad-values.json", fmt)
    base = blend_value_prior(elo, values)

    idx = fmt.team_index()
    for team_id, delta in inputs.rating_overrides.items():
        if team_id not in idx:
            raise UnknownTeamError(team_id)
        base[idx[team_id]] += delta

    resolved_seed = inputs.seed if inputs.seed is not None else int(np.random.default_rng().integers(2**31))
    result = run_tournament(
        fmt,
        EloMatchEngine(fmt, base),
        n_sims=inputs.n_sims,
        seed=resolved_seed,
        results=results,
        fixture_goal_offsets=inputs.fixture_goal_offsets,
    )

    reach = build_team_reach(fmt, result)
    teams = [
        TeamInfo(
            team_id=t.id,
            name=t.name,
            group=t.group,
            elo=round(float(elo[i]), 1),
            rating=round(float(base[i]), 1),
            value_eur_m=float(values[i]),
            champion_prob=reach[t.id]["champion"],
            reach_probs=reach[t.id],
        )
        for i, t in enumerate(fmt.teams)
    ]
    return SimOutputs(
        n_sims=inputs.n_sims,
        seed=resolved_seed,
        focus=build_focus_team(fmt, result, team_id=settings.focus_team),
        slots=build_slots(fmt, result),
        teams=teams,
        groups=build_groups(fmt, result),
        matches=build_matches(fmt, result, played=set(results)),
    )
