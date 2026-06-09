from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wolves.sim.format import GROUPS, FormatData
from wolves.sim.match import expected_score, simulate_goals


class ThirdsAllocationError(Exception):
    def __init__(self, qualified: tuple[str, ...]) -> None:
        self.qualified = qualified
        super().__init__(f"no valid third-place allocation for qualified groups {qualified}")


@dataclass
class SimResult:
    n_sims: int
    rank_in_group: np.ndarray
    third_qualified: np.ndarray
    ko_home: dict[int, np.ndarray]
    ko_away: dict[int, np.ndarray]
    ko_winner: dict[int, np.ndarray]
    ko_loser: dict[int, np.ndarray]


def allocate_thirds(qualified: frozenset[int], slot_elig: list[tuple[int, list[int]]]) -> dict[int, int] | None:
    """Assign the 8 qualified third-placed groups to slots, respecting per-slot eligibility."""
    slots = sorted(slot_elig, key=lambda s: len([g for g in s[1] if g in qualified]))
    assignment: dict[int, int] = {}
    used: set[int] = set()

    def backtrack(i: int) -> bool:
        if i == len(slots):
            return True
        match, elig = slots[i]
        for g in elig:
            if g in qualified and g not in used:
                assignment[match] = g
                used.add(g)
                if backtrack(i + 1):
                    return True
                used.remove(g)
                del assignment[match]
        return False

    return assignment if backtrack(0) else None


def run_tournament(fmt: FormatData, ratings: np.ndarray, *, n_sims: int, seed: int = 0) -> SimResult:
    """Vectorised Monte Carlo over the exact 2026 format.

    Known simplifications: no head-to-head or fair-play tiebreaks (random in
    their place), no hot rating updates, single fixed goal budget, extra time
    folded into one Elo-weighted draw resolution.
    """
    rng = np.random.default_rng(seed)
    idx = fmt.team_index()
    members = fmt.group_members()
    n_teams = len(fmt.teams)

    pts = np.zeros((n_teams, n_sims), dtype=np.int32)
    gf = np.zeros((n_teams, n_sims), dtype=np.int32)
    ga = np.zeros((n_teams, n_sims), dtype=np.int32)

    for m in fmt.group_matches:
        hi, ai = idx[m.home], idx[m.away]
        hg, ag = simulate_goals(rng, ratings[hi], ratings[ai], n_sims)
        pts[hi] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
        pts[ai] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        gf[hi] += hg
        ga[hi] += ag
        gf[ai] += ag
        ga[ai] += hg

    sims = np.arange(n_sims)
    rank_in_group = np.zeros((n_teams, n_sims), dtype=np.int8)
    winner = np.zeros((12, n_sims), dtype=np.int32)
    runner = np.zeros((12, n_sims), dtype=np.int32)
    third = np.zeros((12, n_sims), dtype=np.int32)
    third_pts = np.zeros((12, n_sims), dtype=np.int32)
    third_gd = np.zeros((12, n_sims), dtype=np.int32)
    third_gf = np.zeros((12, n_sims), dtype=np.int32)

    for g_i, g in enumerate(GROUPS):
        tidx = np.array(members[g])
        p, f, a = pts[tidx], gf[tidx], ga[tidx]
        order = np.lexsort((rng.random((4, n_sims)), f, f - a, p), axis=0)
        for k in range(4):
            rank_in_group[tidx[order[3 - k]], sims] = k
        winner[g_i] = tidx[order[3]]
        runner[g_i] = tidx[order[2]]
        third_local = order[1]
        third[g_i] = tidx[third_local]
        third_pts[g_i] = p[third_local, sims]
        third_gd[g_i] = (f - a)[third_local, sims]
        third_gf[g_i] = f[third_local, sims]

    order = np.lexsort((rng.random((12, n_sims)), third_gf, third_gd, third_pts), axis=0)
    third_qualified = np.zeros((12, n_sims), dtype=bool)
    third_qualified[order[4:], sims] = True

    slot_elig = [
        (m.match, [GROUPS.index(g) for g in m.away.removeprefix("3:")]) for m in fmt.knockout if m.away.startswith("3:")
    ]
    key = (third_qualified * (1 << np.arange(12))[:, None]).sum(axis=0)
    third_team: dict[int, np.ndarray] = {match: np.zeros(n_sims, dtype=np.int32) for match, _ in slot_elig}
    for k in np.unique(key):
        qualified = frozenset(g for g in range(12) if k & (1 << g))
        assignment = allocate_thirds(qualified, slot_elig)
        if assignment is None:
            raise ThirdsAllocationError(tuple(GROUPS[g] for g in sorted(qualified)))
        mask = key == k
        for match, g in assignment.items():
            third_team[match][mask] = third[g, mask]

    ko_home: dict[int, np.ndarray] = {}
    ko_away: dict[int, np.ndarray] = {}
    ko_winner: dict[int, np.ndarray] = {}
    ko_loser: dict[int, np.ndarray] = {}

    def resolve(spec: str, match: int) -> np.ndarray:
        if spec.startswith("3:"):
            return third_team[match]
        if spec.startswith("W"):
            return ko_winner[int(spec[1:])]
        if spec.startswith("L"):
            return ko_loser[int(spec[1:])]
        pos, group = int(spec[0]), GROUPS.index(spec[1])
        return winner[group] if pos == 1 else runner[group]

    for m in sorted(fmt.knockout, key=lambda m: m.match):
        h = resolve(m.home, m.match)
        a = resolve(m.away, m.match)
        hg, ag2 = simulate_goals(rng, ratings[h], ratings[a], n_sims)
        home_wins = np.where(hg == ag2, rng.random(n_sims) < expected_score(ratings[h], ratings[a]), hg > ag2)
        ko_home[m.match] = h
        ko_away[m.match] = a
        ko_winner[m.match] = np.where(home_wins, h, a)
        ko_loser[m.match] = np.where(home_wins, a, h)

    return SimResult(
        n_sims=n_sims,
        rank_in_group=rank_in_group,
        third_qualified=third_qualified,
        ko_home=ko_home,
        ko_away=ko_away,
        ko_winner=ko_winner,
        ko_loser=ko_loser,
    )
