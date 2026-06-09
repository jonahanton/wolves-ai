"""K-sample median of the final rating overrides.

The calibration device from Halawi and FutureSearch practice: rerun only the
final extraction over the same dossier and take the per-team median, recording
the spread as a disagreement metric. Replaces reviewer agents."""

from __future__ import annotations

import statistics

from wolves.agent.contracts import Disagreement, RatingOverride


def median_overrides(samples: list[list[RatingOverride]]) -> tuple[list[RatingOverride], Disagreement]:
    """Per-team median delta across samples; teams absent from a sample count as 0."""
    if not samples:
        return [], Disagreement(k=0)

    teams: list[str] = []
    for sample in samples:
        for override in sample:
            if override.team_id not in teams:
                teams.append(override.team_id)

    by_team = {s_id: {o.team_id: o for o in sample} for s_id, sample in enumerate(samples)}
    medians: list[RatingOverride] = []
    spreads: dict[str, float] = {}
    for team in teams:
        deltas = [by_team[i][team].delta_elo if team in by_team[i] else 0.0 for i in range(len(samples))]
        spreads[team] = max(deltas) - min(deltas)
        median = statistics.median(deltas)
        if median == 0.0:
            continue
        template = next(o for sample in samples for o in sample if o.team_id == team)
        medians.append(template.model_copy(update={"delta_elo": median}))

    disagreement = Disagreement(
        k=len(samples),
        per_team_spread=spreads,
        max_spread=max(spreads.values(), default=0.0),
        mean_spread=sum(spreads.values()) / len(spreads) if spreads else 0.0,
    )
    return medians, disagreement
