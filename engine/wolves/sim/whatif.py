from __future__ import annotations

import numpy as np

from wolves.sim.format import FormatData
from wolves.sim.mc import SimResult
from wolves.snapshot import WhatIfFixture, WhatIfOutcome

OUTCOMES = ("win", "draw", "lose")


def build_what_if(
    fmt: FormatData,
    result: SimResult,
    *,
    team_id: str,
    finish_masks: dict[str, np.ndarray],
    finish_cities: dict[str, str],
) -> list[WhatIfFixture]:
    """Conditional finish and R32 city tables for each of England's group fixtures."""
    fixtures = [m for m in fmt.group_matches if team_id in (m.home, m.away)]
    tables: list[WhatIfFixture] = []
    for m in sorted(fixtures, key=lambda m: m.date):
        hg, ag = result.group_goals[m.match]
        own, opp = (hg, ag) if m.home == team_id else (ag, hg)
        opponent_id = m.away if m.home == team_id else m.home
        outcome_masks = {"win": own > opp, "draw": own == opp, "lose": own < opp}
        outcomes = []
        for name in OUTCOMES:
            mask = outcome_masks[name]
            count = int(mask.sum())
            if count == 0:
                continue
            finish_probs = {f: round(float((mask & fm).sum() / count), 4) for f, fm in finish_masks.items()}
            city_probs: dict[str, float] = {}
            for f in ("win_group", "runner_up", "third_qualified"):
                city = finish_cities[f]
                city_probs[city] = city_probs.get(city, 0.0) + float((mask & finish_masks[f]).sum() / count)
            city_probs = {c: round(p, 4) for c, p in city_probs.items()}
            outcomes.append(
                WhatIfOutcome(
                    outcome=name,
                    prob=round(count / result.n_sims, 4),
                    finish_probs=finish_probs,
                    r32_city_probs=city_probs,
                )
            )
        tables.append(
            WhatIfFixture(match=m.match, date=m.date, city=m.city, opponent_id=opponent_id, outcomes=outcomes)
        )
    return tables
