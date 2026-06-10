"""A team's tournament DAG: qualification routes, per-round opponents and
advance probabilities, under any perturbation set. The `title` view conditions
on worlds where the team lifts the trophy; `reach` conditions on playing."""

from __future__ import annotations

from collections import Counter
from typing import Literal

import numpy as np
from pydantic import BaseModel

from wolves.data.teams import registry_team_key
from wolves.forecast import DEFAULT_SIMS, Forecaster, Perturbation
from wolves.sim.mc import SimResult

STAGES = ("r32", "r16", "qf", "sf", "final")
OPPONENTS_SHOWN = 5


class OpponentShare(BaseModel):
    team: str
    share: float
    strength_rank: int


class SlotNode(BaseModel):
    match: int
    share: float
    opponents: list[OpponentShare]


class StageNode(BaseModel):
    stage: str
    p_play: float
    p_advance_given_play: float
    slots: list[SlotNode]


class PathTree(BaseModel):
    team: str
    view: Literal["reach", "title"]
    n_sims: int
    p_champion: float
    qualification: dict[str, float]
    stages: list[StageNode]


def _strength_ranks(forecaster: Forecaster) -> dict[int, int]:
    state = forecaster.state
    index = {team: i for i, team in enumerate(state.teams)}
    strengths = np.array([state.strengths[index[registry_team_key(t.id)]] for t in forecaster.fmt.teams])
    order = np.argsort(-strengths)
    ranks = np.empty_like(order)
    ranks[order] = np.arange(1, len(order) + 1)
    return {i: int(ranks[i]) for i in range(len(order))}


def _qualification(result: SimResult, team_idx: int, condition: np.ndarray) -> dict[str, float]:
    """Group-finish shares; third-place qualification shows up in the r32 stage."""
    rank = result.rank_in_group[team_idx][condition]
    return {
        "win_group": round(float((rank == 0).mean()), 4),
        "runner_up": round(float((rank == 1).mean()), 4),
        "third": round(float((rank == 2).mean()), 4),
        "fourth": round(float((rank == 3).mean()), 4),
    }


def team_path_tree(
    forecaster: Forecaster,
    team: str,
    *,
    view: Literal["reach", "title"] = "reach",
    perturbations: tuple[Perturbation, ...] = (),
    n_sims: int = DEFAULT_SIMS * 5,
    seed: int = 0,
) -> PathTree:
    result = forecaster.simulate(n_sims=n_sims, seed=seed, perturbations=perturbations, parameter_uncertainty=False)
    ids = [t.id for t in forecaster.fmt.teams]
    team_idx = ids.index(team)
    ranks = _strength_ranks(forecaster)

    final = max(m.match for m in forecaster.fmt.knockout if m.stage == "final")
    champion = result.ko_winner[final] == team_idx
    condition = champion if view == "title" else np.ones(n_sims, dtype=bool)
    denominator = max(int(condition.sum()), 1)

    by_stage: dict[str, list[int]] = {stage: [] for stage in STAGES}
    for m in forecaster.fmt.knockout:
        if m.stage in by_stage:
            by_stage[m.stage].append(m.match)

    stages: list[StageNode] = []
    for stage in STAGES:
        slots: list[SlotNode] = []
        played = np.zeros(n_sims, dtype=bool)
        advanced = np.zeros(n_sims, dtype=bool)
        for match in by_stage[stage]:
            home, away = result.ko_home[match], result.ko_away[match]
            involved = ((home == team_idx) | (away == team_idx)) & condition
            if not involved.any():
                continue
            played |= involved
            advanced |= involved & (result.ko_winner[match] == team_idx)
            opponents = np.where(home[involved] == team_idx, away[involved], home[involved])
            top = Counter(opponents.tolist()).most_common(OPPONENTS_SHOWN)
            slots.append(
                SlotNode(
                    match=match,
                    share=round(float(involved.sum() / denominator), 4),
                    opponents=[
                        OpponentShare(team=ids[opp], share=round(count / len(opponents), 4), strength_rank=ranks[opp])
                        for opp, count in top
                    ],
                )
            )
        n_played = int(played.sum())
        stages.append(
            StageNode(
                stage=stage,
                p_play=round(n_played / denominator, 4),
                p_advance_given_play=round(float(advanced.sum() / n_played), 4) if n_played else 0.0,
                slots=sorted(slots, key=lambda s: -s.share),
            )
        )

    return PathTree(
        team=team,
        view=view,
        n_sims=n_sims,
        p_champion=round(float(champion.mean()), 4),
        qualification=_qualification(result, team_idx, condition),
        stages=stages,
    )
