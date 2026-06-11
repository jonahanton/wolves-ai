from __future__ import annotations

import json
from typing import TYPE_CHECKING

from wolves_backend.models import TeamHistoryPoint

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wolves_backend.models import SnapshotRef


def team_history_points(team_id: str, snapshots: Iterable[tuple[SnapshotRef, str | None]]) -> list[TeamHistoryPoint]:
    """Extract one team's forecast series from snapshot bodies, oldest first."""
    points = []
    for ref, body in snapshots:
        team = _team_block(team_id, body)
        if team is None:
            continue
        points.append(
            TeamHistoryPoint(
                run_id=ref.run_id,
                as_of=ref.as_of,
                champion_prob=float(team.get("champion_prob", 0.0)),
                reach_probs={stage: float(prob) for stage, prob in dict(team.get("reach_probs") or {}).items()},
            )
        )
    points.sort(key=lambda point: (point.as_of, point.run_id))
    return points


def _team_block(team_id: str, body: str | None) -> dict | None:
    if body is None:
        return None
    try:
        snapshot = json.loads(body)
    except ValueError:
        return None
    teams = snapshot.get("teams") if isinstance(snapshot, dict) else None
    if not isinstance(teams, list):
        return None
    return next((team for team in teams if isinstance(team, dict) and team.get("team_id") == team_id), None)
