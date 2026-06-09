from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wolves.sim.elo import rating_delta
from wolves.sim.format import GROUPS, FormatData, GroupMatch, PlayedResult
from wolves.sim.match import STAGE_GAP_MULT, goal_means, knockout_home_wins, simulate_goals
from wolves.sim.tiebreaks import rank_group, rank_thirds
from wolves.sim.venues import venue_bonus_table

RATING_SIGMA = 35.0
MIN_GOAL_MEAN_AFTER_OFFSET = 0.05


class ThirdsAllocationError(Exception):
    def __init__(self, qualified: tuple[str, ...]) -> None:
        self.qualified = qualified
        super().__init__(f"no valid third-place allocation for qualified groups {qualified}")


@dataclass
class KnockoutTieStats:
    """Per-slot aggregates for the modal pairing; win/decided/modal-score
    figures are conditional on that pairing occurring."""

    home: int
    away: int
    p_pairing: float
    p_home_win: float
    p_decided_90: float
    modal_score: tuple[int, int]


@dataclass
class SimResult:
    n_sims: int
    rank_in_group: np.ndarray
    third_qualified: np.ndarray
    group_points: np.ndarray
    group_goals: dict[int, tuple[np.ndarray, np.ndarray]]
    ko_home: dict[int, np.ndarray]
    ko_away: dict[int, np.ndarray]
    ko_winner: dict[int, np.ndarray]
    ko_loser: dict[int, np.ndarray]
    ko_stats: dict[int, KnockoutTieStats]


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


def run_tournament(
    fmt: FormatData,
    base_ratings: np.ndarray,
    *,
    n_sims: int,
    seed: int = 0,
    rating_sigma: float = RATING_SIGMA,
    results: dict[int, PlayedResult] | None = None,
    fixture_goal_offsets: dict[int, tuple[float, float]] | None = None,
) -> SimResult:
    """Vectorised Monte Carlo over the exact 2026 format with hot in-sim Elo updates."""
    rng = np.random.default_rng(seed)
    idx = fmt.team_index()
    members = fmt.group_members()
    n_teams = len(fmt.teams)
    played = results or {}
    offsets = fixture_goal_offsets or {}
    bonus = venue_bonus_table(fmt)
    sims = np.arange(n_sims)

    ratings = base_ratings[:, None] + rng.normal(0.0, rating_sigma, (n_teams, n_sims))

    def match_lambdas(
        home: np.ndarray, away: np.ndarray, city: str, stage: str, match: int
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        diff = STAGE_GAP_MULT[stage] * (ratings[home, sims] - ratings[away, sims]) + (
            bonus[city][home] - bonus[city][away]
        )
        lam_h, lam_a = goal_means(diff)
        if match in offsets:
            off_h, off_a = offsets[match]
            lam_h = np.maximum(lam_h + off_h, MIN_GOAL_MEAN_AFTER_OFFSET)
            lam_a = np.maximum(lam_a + off_a, MIN_GOAL_MEAN_AFTER_OFFSET)
        return diff, lam_h, lam_a

    pts = np.zeros((n_teams, n_sims), dtype=np.int32)
    gf = np.zeros((n_teams, n_sims), dtype=np.int32)
    ga = np.zeros((n_teams, n_sims), dtype=np.int32)
    group_goals: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for m in sorted(fmt.group_matches, key=lambda m: m.date):
        hi, ai = idx[m.home], idx[m.away]
        diff, lam_h, lam_a = match_lambdas(np.full(n_sims, hi), np.full(n_sims, ai), m.city, "group", m.match)
        if m.match in played:
            r = played[m.match]
            hg = np.full(n_sims, r.home_goals, dtype=np.int16)
            ag = np.full(n_sims, r.away_goals, dtype=np.int16)
        else:
            hg_raw, ag_raw = simulate_goals(rng, lam_h, lam_a)
            hg, ag = hg_raw.astype(np.int16), ag_raw.astype(np.int16)
        group_goals[m.match] = (hg, ag)
        pts[hi] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
        pts[ai] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        gf[hi] += hg
        ga[hi] += ag
        gf[ai] += ag
        ga[ai] += hg
        delta = rating_delta(diff, hg, ag, stage="group")
        ratings[hi] += delta
        ratings[ai] -= delta

    matches_by_group: dict[str, list[GroupMatch]] = {g: [] for g in GROUPS}
    for m in fmt.group_matches:
        matches_by_group[m.group].append(m)

    rank_in_group = np.zeros((n_teams, n_sims), dtype=np.int8)
    winner = np.zeros((12, n_sims), dtype=np.int32)
    runner = np.zeros((12, n_sims), dtype=np.int32)
    third = np.zeros((12, n_sims), dtype=np.int32)
    third_pts = np.zeros((12, n_sims), dtype=np.int32)
    third_gd = np.zeros((12, n_sims), dtype=np.int32)
    third_gf = np.zeros((12, n_sims), dtype=np.int32)

    for g_i, g in enumerate(GROUPS):
        tidx = np.array(members[g])
        local = {t: k for k, t in enumerate(tidx)}
        h2h_pts = np.zeros((4, 4, n_sims), dtype=np.int16)
        h2h_gd = np.zeros((4, 4, n_sims), dtype=np.int16)
        h2h_gf = np.zeros((4, 4, n_sims), dtype=np.int16)
        for m in matches_by_group[g]:
            i, j = local[idx[m.home]], local[idx[m.away]]
            hg, ag = group_goals[m.match]
            h2h_pts[i, j] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0)).astype(np.int16)
            h2h_pts[j, i] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0)).astype(np.int16)
            h2h_gd[i, j] += hg - ag
            h2h_gd[j, i] += ag - hg
            h2h_gf[i, j] += hg
            h2h_gf[j, i] += ag
        p, f, a = pts[tidx], gf[tidx], ga[tidx]
        order = rank_group(rng, p, f - a, f, h2h_pts, h2h_gd, h2h_gf)
        for k in range(4):
            rank_in_group[tidx[order[3 - k]], sims] = k
        winner[g_i] = tidx[order[3]]
        runner[g_i] = tidx[order[2]]
        third_local = order[1]
        third[g_i] = tidx[third_local]
        third_pts[g_i] = p[third_local, sims]
        third_gd[g_i] = (f - a)[third_local, sims]
        third_gf[g_i] = f[third_local, sims]

    order = rank_thirds(rng, third_pts, third_gd, third_gf)
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
    ko_stats: dict[int, KnockoutTieStats] = {}

    def tie_stats(
        h: np.ndarray, a: np.ndarray, hg: np.ndarray, ag: np.ndarray, home_wins: np.ndarray
    ) -> KnockoutTieStats:
        pairs = h.astype(np.int64) * n_teams + a
        values, counts = np.unique(pairs, return_counts=True)
        modal_pair = int(values[np.argmax(counts)])
        mask = pairs == modal_pair
        scores = hg[mask].astype(np.int64) * 1_000 + ag[mask]
        score_values, score_counts = np.unique(scores, return_counts=True)
        modal_score = int(score_values[np.argmax(score_counts)])
        return KnockoutTieStats(
            home=modal_pair // n_teams,
            away=modal_pair % n_teams,
            p_pairing=float(counts.max() / n_sims),
            p_home_win=float(home_wins[mask].mean()),
            p_decided_90=float((hg[mask] != ag[mask]).mean()),
            modal_score=(modal_score // 1_000, modal_score % 1_000),
        )

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
        diff, lam_h, lam_a = match_lambdas(h, a, m.city, "knockout", m.match)
        if m.match in played:
            r = played[m.match]
            hg = np.full(n_sims, r.home_goals, dtype=np.int16)
            ag = np.full(n_sims, r.away_goals, dtype=np.int16)
            home_wins = (h == idx[r.winner]) if r.winner is not None else np.repeat(hg[0] > ag[0], n_sims)
        else:
            hg_raw, ag_raw = simulate_goals(rng, lam_h, lam_a)
            hg, ag = hg_raw.astype(np.int16), ag_raw.astype(np.int16)
            home_wins = knockout_home_wins(rng, diff, hg, ag)
            ko_stats[m.match] = tie_stats(h, a, hg, ag, home_wins)
        # eloratings.net scores shootout wins as one-goal wins, so the hot update mirrors that.
        elo_hg = np.where(hg == ag, hg + home_wins, hg)
        elo_ag = np.where(hg == ag, ag + ~home_wins, ag)
        delta = rating_delta(diff, elo_hg, elo_ag, stage="knockout")
        ratings[h, sims] += delta
        ratings[a, sims] -= delta
        ko_home[m.match] = h
        ko_away[m.match] = a
        ko_winner[m.match] = np.where(home_wins, h, a)
        ko_loser[m.match] = np.where(home_wins, a, h)

    return SimResult(
        n_sims=n_sims,
        rank_in_group=rank_in_group,
        third_qualified=third_qualified,
        group_points=pts,
        group_goals=group_goals,
        ko_home=ko_home,
        ko_away=ko_away,
        ko_winner=ko_winner,
        ko_loser=ko_loser,
        ko_stats=ko_stats,
    )
