from __future__ import annotations

import numpy as np

from wolves.sim.format import FormatData
from wolves.sim.mc import SimResult
from wolves.snapshot import LockDate

MATCHES_PER_MATCHDAY = 2
GAMES_PER_TEAM = 3


def build_lock_dates(
    fmt: FormatData,
    result: SimResult,
    *,
    team_id: str,
    group: str,
    finish_masks: dict[str, np.ndarray],
    finish_cities: dict[str, str],
) -> list[LockDate]:
    """Probability the team's R32 city is mathematically certain after each group matchday.

    Before the group completes, the city can only lock by the team being
    unreachable at the top (a strict points lead beats any remaining result;
    equal points could fall to tiebreaks either way). Once the whole group
    stage ends, finish and thirds allocation are fully determined.
    """
    idx = fmt.team_index()
    e = idx[team_id]
    group_matches = sorted((m for m in fmt.group_matches if m.group == group), key=lambda m: m.date)
    member_ids = [idx[t.id] for t in fmt.teams if t.group == group]

    n = result.n_sims
    pts = {t: np.zeros(n, dtype=np.int32) for t in member_ids}
    locks: list[LockDate] = []

    for md in range(GAMES_PER_TEAM):
        chunk = group_matches[md * MATCHES_PER_MATCHDAY : (md + 1) * MATCHES_PER_MATCHDAY]
        for m in chunk:
            hg, ag = result.group_goals[m.match]
            pts[idx[m.home]] += np.where(hg > ag, 3, np.where(hg == ag, 1, 0))
            pts[idx[m.away]] += np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        remaining = GAMES_PER_TEAM - (md + 1)
        if remaining == 0:
            continue
        locked = np.ones(n, dtype=bool)
        for o in member_ids:
            if o != e:
                locked &= pts[o] + 3 * remaining < pts[e]
        prob = float(locked.mean())
        date = max(m.date for m in chunk)
        city = finish_cities["win_group"]
        locks.append(
            LockDate(date=date, prob_locked=round(prob, 4), locked_city_probs={city: round(prob, 4)} if prob else {})
        )

    end_date = max(m.date for m in fmt.group_matches)
    city_probs: dict[str, float] = {}
    for f in ("win_group", "runner_up", "third_qualified"):
        city = finish_cities[f]
        city_probs[city] = round(city_probs.get(city, 0.0) + float(finish_masks[f].mean()), 4)
    locks.append(LockDate(date=end_date, prob_locked=1.0, locked_city_probs=city_probs))
    return locks
