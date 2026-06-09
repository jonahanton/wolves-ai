from __future__ import annotations

import numpy as np

from wolves.sim.format import GROUPS, FormatData
from wolves.sim.mc import SimResult
from wolves.snapshot import Candidate, EnglandBlock, EnglandPath, Slot, SlotSide

ENGLAND = "england"
TOP_CANDIDATES = 6

FINISH_SLOTS = {"win_group": "1L", "runner_up": "2L", "third": "3"}


def _candidates(fmt: FormatData, teams: np.ndarray, weight: float = 1.0) -> list[Candidate]:
    if teams.size == 0:
        return []
    counts = np.bincount(teams, minlength=len(fmt.teams)) / teams.size
    top = np.argsort(counts)[::-1][:TOP_CANDIDATES]
    return [
        Candidate(team_id=fmt.teams[int(i)].id, prob=round(float(counts[i]) * weight, 4)) for i in top if counts[i] > 0
    ]


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


def _england_r32_match(fmt: FormatData, finish: str) -> tuple[int, bool]:
    """Return (match number, england_is_home) for England's R32 slot given a group finish."""
    spec = FINISH_SLOTS[finish]
    for m in fmt.knockout:
        if m.stage != "r32":
            continue
        if finish == "third":
            if m.away.startswith("3:") and "L" in m.away.removeprefix("3:"):
                return m.match, False
        elif m.home == spec:
            return m.match, True
        elif m.away == spec:
            return m.match, False
    raise LookupError(f"no R32 slot for England finish {finish!r}")


def build_england(fmt: FormatData, result: SimResult) -> EnglandBlock:
    idx = fmt.team_index()
    e = idx[ENGLAND]
    group_i = GROUPS.index("L")
    rank = result.rank_in_group[e]
    n = result.n_sims

    third_q = (rank == 2) & result.third_qualified[group_i]
    finish_probs = {
        "win_group": float((rank == 0).mean()),
        "runner_up": float((rank == 1).mean()),
        "third_qualified": float(third_q.mean()),
        "third_eliminated": float(((rank == 2) & ~result.third_qualified[group_i]).mean()),
        "fourth": float((rank == 3).mean()),
    }

    r32_matches = [m.match for m in fmt.knockout if m.stage == "r32"]
    stage_matches = {
        "r16": [m.match for m in fmt.knockout if m.stage == "r16"],
        "qf": [m.match for m in fmt.knockout if m.stage == "qf"],
        "sf": [m.match for m in fmt.knockout if m.stage == "sf"],
        "final": [m.match for m in fmt.knockout if m.stage == "final"],
    }

    def won_any(matches: list[int]) -> np.ndarray:
        out = np.zeros(n, dtype=bool)
        for match in matches:
            out |= result.ko_winner[match] == e
        return out

    in_r32 = (rank <= 1) | third_q
    reach_probs = {
        "r32": float(in_r32.mean()),
        "r16": float(won_any(r32_matches).mean()),
        "qf": float(won_any(stage_matches["r16"]).mean()),
        "sf": float(won_any(stage_matches["qf"]).mean()),
        "final": float(won_any(stage_matches["sf"]).mean()),
        "champion": float(won_any(stage_matches["final"]).mean()),
    }

    masks = {"win_group": rank == 0, "runner_up": rank == 1, "third": third_q}
    paths = []
    for finish, mask in masks.items():
        match, is_home = _england_r32_match(fmt, finish)
        ko = fmt.knockout[[m.match for m in fmt.knockout].index(match)]
        opponents = result.ko_away[match][mask] if is_home else result.ko_home[match][mask]
        paths.append(
            EnglandPath(
                finish=finish,
                prob=round(float(mask.mean()), 4),
                r32_match=match,
                city=ko.city,
                date=ko.date,
                opponents=_candidates(fmt, opponents),
            )
        )

    return EnglandBlock(
        team_id=ENGLAND,
        group="L",
        finish_probs={k: round(v, 4) for k, v in finish_probs.items()},
        reach_probs={k: round(v, 4) for k, v in reach_probs.items()},
        paths=paths,
    )
