from __future__ import annotations

import numpy as np

from wolves.sim.format import GROUPS, FormatData, KnockoutMatch
from wolves.sim.lock import build_lock_dates
from wolves.sim.mc import SimResult
from wolves.sim.whatif import build_what_if
from wolves.snapshot import (
    Candidate,
    CityProb,
    EnglandBlock,
    EnglandPath,
    ModalStep,
    RoundOpponents,
    Slot,
    SlotSide,
)

ENGLAND = "england"
ENGLAND_GROUP = "L"
TOP_CANDIDATES = 6
ONWARD_ROUNDS = ("r16", "qf")
KO_ROUNDS = ("r32", "r16", "qf", "sf", "final")

FINISH_SLOTS = {"win_group": "1L", "runner_up": "2L", "third": "3"}


def _candidates(fmt: FormatData, teams: np.ndarray) -> list[Candidate]:
    if teams.size == 0:
        return []
    counts = np.bincount(teams, minlength=len(fmt.teams)) / teams.size
    top = np.argsort(counts)[::-1][:TOP_CANDIDATES]
    return [Candidate(team_id=fmt.teams[int(i)].id, prob=round(float(counts[i]), 4)) for i in top if counts[i] > 0]


def build_slots(fmt: FormatData, result: SimResult) -> list[Slot]:
    return [
        Slot(
            match=m.match,
            stage=m.stage,
            date=m.date,
            city=m.city,
            home=SlotSide(label=m.home, candidates=_candidates(fmt, result.ko_home[m.match])),
            away=SlotSide(label=m.away, candidates=_candidates(fmt, result.ko_away[m.match])),
        )
        for m in fmt.knockout
    ]


def champion_probs(fmt: FormatData, result: SimResult) -> dict[str, float]:
    """Per-team probability of winning the final."""
    final = max(m.match for m in fmt.knockout)
    counts = np.bincount(result.ko_winner[final], minlength=len(fmt.teams)) / result.n_sims
    return {t.id: round(float(counts[i]), 4) for i, t in enumerate(fmt.teams)}


def _england_r32_match(fmt: FormatData, finish: str) -> tuple[int, bool]:
    """Return (match number, england_is_home) for England's R32 slot given a group finish."""
    spec = FINISH_SLOTS[finish]
    for m in fmt.knockout:
        if m.stage != "r32":
            continue
        if finish == "third":
            if m.away.startswith("3:") and ENGLAND_GROUP in m.away.removeprefix("3:"):
                return m.match, False
        elif m.home == spec:
            return m.match, True
        elif m.away == spec:
            return m.match, False
    raise LookupError(f"no R32 slot for England finish {finish!r}")


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


def _build_paths(fmt: FormatData, result: SimResult, e: int, path_masks: dict[str, np.ndarray]) -> list[EnglandPath]:
    paths = []
    for finish, mask in path_masks.items():
        match, is_home = _england_r32_match(fmt, finish)
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
            EnglandPath(
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


def _build_modal_path(fmt: FormatData, result: SimResult, e: int, path_masks: dict[str, np.ndarray]) -> list[ModalStep]:
    finish = max(path_masks, key=lambda f: path_masks[f].sum())
    mask = path_masks[finish]
    r32_match, _ = _england_r32_match(fmt, finish)
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


def build_england(fmt: FormatData, result: SimResult) -> EnglandBlock:
    idx = fmt.team_index()
    e = idx[ENGLAND]
    group_i = GROUPS.index(ENGLAND_GROUP)
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
        f: next(m for m in fmt.knockout if m.match == _england_r32_match(fmt, p)[0]).city
        for f, p in (("win_group", "win_group"), ("runner_up", "runner_up"), ("third_qualified", "third"))
    }

    return EnglandBlock(
        team_id=ENGLAND,
        group=ENGLAND_GROUP,
        finish_probs={k: round(v, 4) for k, v in finish_probs.items()},
        reach_probs={k: round(v, 4) for k, v in reach_probs.items()},
        paths=_build_paths(fmt, result, e, path_masks),
        modal_path=_build_modal_path(fmt, result, e, path_masks),
        city_probs=_build_city_probs(fmt, result, e),
        lock_dates=build_lock_dates(
            fmt, result, team_id=ENGLAND, group=ENGLAND_GROUP, finish_masks=finish_masks, finish_cities=finish_cities
        ),
        what_if=build_what_if(fmt, result, team_id=ENGLAND, finish_masks=finish_masks, finish_cities=finish_cities),
    )
