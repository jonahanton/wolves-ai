from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from wolves.sim.format import GROUPS, FormatData, KnockoutMatch
from wolves.sim.lock import build_lock_dates
from wolves.sim.mc import SimResult
from wolves.sim.whatif import build_what_if
from wolves.snapshot import (
    Candidate,
    CityProb,
    FocusTeamBlock,
    FocusTeamPath,
    GroupBlock,
    GroupTeamStanding,
    MatchProbs,
    ModalStep,
    RoundOpponents,
    Slot,
    SlotSide,
)

TOP_CANDIDATES = 6
ONWARD_ROUNDS = ("r16", "qf")
KO_ROUNDS = ("r32", "r16", "qf", "sf", "final")


def _top_candidates(fmt: FormatData, probs: np.ndarray) -> list[Candidate]:
    top = np.argsort(probs)[::-1][:TOP_CANDIDATES]
    return [Candidate(team_id=fmt.teams[int(i)].id, prob=round(float(probs[i]), 4)) for i in top if probs[i] > 0]


def _candidates(fmt: FormatData, teams: np.ndarray) -> list[Candidate]:
    if teams.size == 0:
        return []
    return _top_candidates(fmt, np.bincount(teams, minlength=len(fmt.teams)) / teams.size)


def _slot_occupancy(fmt: FormatData, result: SimResult) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Per-slot team-occupancy probabilities for each side, as full team-length vectors."""
    n_teams = len(fmt.teams)
    return {
        m.match: (
            np.bincount(result.ko_home[m.match], minlength=n_teams) / result.n_sims,
            np.bincount(result.ko_away[m.match], minlength=n_teams) / result.n_sims,
        )
        for m in fmt.knockout
    }


def _slots_from_occupancy(fmt: FormatData, occupancy: Mapping[int, tuple[np.ndarray, np.ndarray]]) -> list[Slot]:
    return [
        Slot(
            match=m.match,
            stage=m.stage,
            date=m.date,
            city=m.city,
            home=SlotSide(label=m.home, candidates=_top_candidates(fmt, occupancy[m.match][0])),
            away=SlotSide(label=m.away, candidates=_top_candidates(fmt, occupancy[m.match][1])),
        )
        for m in fmt.knockout
    ]


def build_slots(fmt: FormatData, result: SimResult) -> list[Slot]:
    return _slots_from_occupancy(fmt, _slot_occupancy(fmt, result))


def build_mixed_slots(fmt: FormatData, weighted: Mapping[str, tuple[float, SimResult]]) -> list[Slot]:
    """Slot candidates mixed across worlds, so each side's probabilities are the
    weight-average of its per-world occupancy and stay coherent with mixed reach."""
    per_world = {name: _slot_occupancy(fmt, result) for name, (_, result) in weighted.items()}
    mixed: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for m in fmt.knockout:
        home = sum(weight * per_world[name][m.match][0] for name, (weight, _) in weighted.items())
        away = sum(weight * per_world[name][m.match][1] for name, (weight, _) in weighted.items())
        mixed[m.match] = (home, away)
    return _slots_from_occupancy(fmt, mixed)


def build_team_reach(fmt: FormatData, result: SimResult) -> dict[str, dict[str, float]]:
    """Per-team probability of reaching each knockout round, ending in champion."""
    n_teams = len(fmt.teams)
    final = max(m.match for m in fmt.knockout if m.stage == "final")
    reached = {"r32": np.zeros(n_teams), "champion": np.bincount(result.ko_winner[final], minlength=n_teams)}
    next_round = {"r32": "r16", "r16": "qf", "qf": "sf", "sf": "final"}
    for m in fmt.knockout:
        if m.stage == "r32":
            reached["r32"] += np.bincount(result.ko_home[m.match], minlength=n_teams)
            reached["r32"] += np.bincount(result.ko_away[m.match], minlength=n_teams)
        if m.stage in next_round:
            target = next_round[m.stage]
            reached.setdefault(target, np.zeros(n_teams))
            reached[target] = reached[target] + np.bincount(result.ko_winner[m.match], minlength=n_teams)
    return {
        t.id: {rnd: round(float(reached[rnd][i] / result.n_sims), 4) for rnd in (*KO_ROUNDS, "champion")}
        for i, t in enumerate(fmt.teams)
    }


GROUP_FINISH_KEYS = ("win_group", "runner_up", "third_qualified", "third_eliminated", "fourth")


def build_groups(fmt: FormatData, result: SimResult) -> list[GroupBlock]:
    """Per-team group finish distributions and expected points, by group."""
    members = fmt.group_members()
    expected = result.group_points.mean(axis=1)
    blocks = []
    for g_i, g in enumerate(GROUPS):
        standings = []
        for i in members[g]:
            rank = result.rank_in_group[i]
            third = rank == 2
            finish = {
                "win_group": (rank == 0).mean(),
                "runner_up": (rank == 1).mean(),
                "third_qualified": (third & result.third_qualified[g_i]).mean(),
                "third_eliminated": (third & ~result.third_qualified[g_i]).mean(),
                "fourth": (rank == 3).mean(),
            }
            standings.append(
                GroupTeamStanding(
                    team_id=fmt.teams[i].id,
                    finish_probs={k: round(float(v), 4) for k, v in finish.items()},
                    expected_points=round(float(expected[i]), 2),
                )
            )
        blocks.append(GroupBlock(group=g, teams=standings))
    return blocks


def build_matches(fmt: FormatData, result: SimResult, *, played: set[int]) -> list[MatchProbs]:
    """Forecast entries for every match without a played result."""
    out = []
    for m in sorted(fmt.group_matches, key=lambda m: m.match):
        if m.match in played:
            continue
        hg, ag = result.group_goals[m.match]
        scores = hg.astype(np.int64) * 1_000 + ag
        values, counts = np.unique(scores, return_counts=True)
        modal = int(values[np.argmax(counts)])
        out.append(
            MatchProbs(
                match=m.match,
                stage="group",
                date=m.date,
                city=m.city,
                home_id=m.home,
                away_id=m.away,
                p_home=round(float((hg > ag).mean()), 4),
                p_away=round(float((hg < ag).mean()), 4),
                p_draw=round(float((hg == ag).mean()), 4),
                modal_score=f"{modal // 1_000}-{modal % 1_000}",
            )
        )
    for m in sorted(fmt.knockout, key=lambda m: m.match):
        if m.match in played or m.match not in result.ko_stats:
            continue
        stats = result.ko_stats[m.match]
        out.append(
            MatchProbs(
                match=m.match,
                stage=m.stage,
                date=m.date,
                city=m.city,
                home_id=fmt.teams[stats.home].id,
                away_id=fmt.teams[stats.away].id,
                p_home=round(stats.p_home_win, 4),
                p_away=round(1.0 - stats.p_home_win, 4),
                p_decided_90=round(stats.p_decided_90, 4),
                p_pairing=round(stats.p_pairing, 4),
                modal_score=f"{stats.modal_score[0]}-{stats.modal_score[1]}",
            )
        )
    return out


def _r32_match(fmt: FormatData, group: str, finish: str) -> tuple[int, bool]:
    """Return (match number, team_is_home) for the team's R32 slot given a group finish."""
    spec = {"win_group": f"1{group}", "runner_up": f"2{group}", "third": "3"}[finish]
    for m in fmt.knockout:
        if m.stage != "r32":
            continue
        if finish == "third":
            if m.away.startswith("3:") and group in m.away.removeprefix("3:"):
                return m.match, False
        elif m.home == spec:
            return m.match, True
        elif m.away == spec:
            return m.match, False
    raise LookupError(f"no R32 slot for group {group} finish {finish!r}")


def _bracket_path(fmt: FormatData, r32_match: int) -> dict[str, KnockoutMatch]:
    """Walk the winners' bracket from an R32 match through to the final."""
    path: dict[str, KnockoutMatch] = {}
    current = r32_match
    while "final" not in path:
        nxt = next(m for m in fmt.knockout if f"W{current}" in (m.home, m.away))
        path[nxt.stage] = nxt
        current = nxt.match
    return path


def _in_match(result: SimResult, match: int, e: int) -> np.ndarray:
    return (result.ko_home[match] == e) | (result.ko_away[match] == e)


def _opponents_in_match(result: SimResult, match: int, e: int, mask: np.ndarray) -> np.ndarray:
    other = np.where(result.ko_home[match] == e, result.ko_away[match], result.ko_home[match])
    return other[mask]


def _build_paths(
    fmt: FormatData, result: SimResult, e: int, group: str, path_masks: dict[str, np.ndarray]
) -> list[FocusTeamPath]:
    paths = []
    for finish, mask in path_masks.items():
        match, is_home = _r32_match(fmt, group, finish)
        ko = next(m for m in fmt.knockout if m.match == match)
        opponents = result.ko_away[match][mask] if is_home else result.ko_home[match][mask]
        bracket = _bracket_path(fmt, match)
        onward = []
        n_finish = int(mask.sum())
        for rnd in ONWARD_ROUNDS:
            rm = bracket[rnd]
            here = mask & _in_match(result, rm.match, e)
            onward.append(
                RoundOpponents(
                    round=rnd,
                    match=rm.match,
                    city=rm.city,
                    date=rm.date,
                    reach_prob=round(int(here.sum()) / n_finish, 4) if n_finish else 0.0,
                    opponents=_candidates(fmt, _opponents_in_match(result, rm.match, e, here)),
                )
            )
        paths.append(
            FocusTeamPath(
                finish=finish,
                prob=round(float(mask.mean()), 4),
                r32_match=match,
                city=ko.city,
                date=ko.date,
                opponents=_candidates(fmt, opponents),
                onward=onward,
            )
        )
    return paths


def _build_modal_path(
    fmt: FormatData, result: SimResult, e: int, group: str, path_masks: dict[str, np.ndarray]
) -> list[ModalStep]:
    finish = max(path_masks, key=lambda f: path_masks[f].sum())
    mask = path_masks[finish]
    r32_match, _ = _r32_match(fmt, group, finish)
    bracket = _bracket_path(fmt, r32_match)
    rounds = [("r32", next(m for m in fmt.knockout if m.match == r32_match))]
    rounds += [(rnd, bracket[rnd]) for rnd in ("r16", "qf", "sf", "final")]

    steps: list[ModalStep] = []
    used: set[int] = set()
    for rnd, km in rounds:
        here = mask & _in_match(result, km.match, e)
        n_here = int(here.sum())
        if n_here == 0:
            break
        counts = np.bincount(_opponents_in_match(result, km.match, e, here), minlength=len(fmt.teams))
        for u in used:
            counts[u] = 0
        pick = int(np.argmax(counts))
        used.add(pick)
        steps.append(
            ModalStep(
                round=rnd,
                match=km.match,
                city=km.city,
                date=km.date,
                opponent_id=fmt.teams[pick].id,
                opponent_prob=round(float(counts[pick] / n_here), 4),
            )
        )
    return steps


def _build_city_probs(fmt: FormatData, result: SimResult, e: int) -> dict[str, list[CityProb]]:
    out: dict[str, list[CityProb]] = {}
    for rnd in KO_ROUNDS:
        by_city: dict[str, float] = {}
        for m in fmt.knockout:
            if m.stage != rnd:
                continue
            p = float(_in_match(result, m.match, e).mean())
            if p > 0:
                by_city[m.city] = by_city.get(m.city, 0.0) + p
        out[rnd] = [CityProb(city=c, prob=round(p, 4)) for c, p in sorted(by_city.items(), key=lambda x: -x[1])]
    return out


def build_focus_team(fmt: FormatData, result: SimResult, *, team_id: str) -> FocusTeamBlock:
    idx = fmt.team_index()
    e = idx[team_id]
    group = next(t.group for t in fmt.teams if t.id == team_id)
    group_i = GROUPS.index(group)
    rank = result.rank_in_group[e]
    n = result.n_sims

    third_q = (rank == 2) & result.third_qualified[group_i]
    finish_masks = {
        "win_group": rank == 0,
        "runner_up": rank == 1,
        "third_qualified": third_q,
        "third_eliminated": (rank == 2) & ~result.third_qualified[group_i],
        "fourth": rank == 3,
    }
    finish_probs = {k: float(m.mean()) for k, m in finish_masks.items()}

    stage_matches = {s: [m.match for m in fmt.knockout if m.stage == s] for s in KO_ROUNDS}

    def won_any(matches: list[int]) -> np.ndarray:
        out = np.zeros(n, dtype=bool)
        for match in matches:
            out |= result.ko_winner[match] == e
        return out

    in_r32 = (rank <= 1) | third_q
    reach_probs = {
        "r32": float(in_r32.mean()),
        "r16": float(won_any(stage_matches["r32"]).mean()),
        "qf": float(won_any(stage_matches["r16"]).mean()),
        "sf": float(won_any(stage_matches["qf"]).mean()),
        "final": float(won_any(stage_matches["sf"]).mean()),
        "champion": float(won_any(stage_matches["final"]).mean()),
    }

    path_masks = {
        "win_group": finish_masks["win_group"],
        "runner_up": finish_masks["runner_up"],
        "third": finish_masks["third_qualified"],
    }
    finish_cities = {
        f: next(m for m in fmt.knockout if m.match == _r32_match(fmt, group, p)[0]).city
        for f, p in (("win_group", "win_group"), ("runner_up", "runner_up"), ("third_qualified", "third"))
    }

    return FocusTeamBlock(
        team_id=team_id,
        group=group,
        finish_probs={k: round(v, 4) for k, v in finish_probs.items()},
        reach_probs={k: round(v, 4) for k, v in reach_probs.items()},
        paths=_build_paths(fmt, result, e, group, path_masks),
        modal_path=_build_modal_path(fmt, result, e, group, path_masks),
        city_probs=_build_city_probs(fmt, result, e),
        lock_dates=build_lock_dates(
            fmt, result, team_id=team_id, group=group, finish_masks=finish_masks, finish_cities=finish_cities
        ),
        what_if=build_what_if(fmt, result, team_id=team_id, finish_masks=finish_masks, finish_cities=finish_cities),
    )
