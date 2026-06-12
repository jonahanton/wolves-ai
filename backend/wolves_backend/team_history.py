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
        snapshot = _parse(body)
        if snapshot is None:
            continue
        team = _team_block(team_id, snapshot)
        if team is None:
            continue
        markets = snapshot.get("markets")
        markets = markets if isinstance(markets, dict) else {}
        points.append(
            TeamHistoryPoint(
                run_id=ref.run_id,
                as_of=ref.as_of,
                champion_prob=float(team.get("champion_prob", 0.0)),
                reach_probs={stage: float(prob) for stage, prob in dict(team.get("reach_probs") or {}).items()},
                market_prob=_market_value(markets, "market_probs", team_id),
                blend_prob=_market_value(markets, "blend_probs", team_id),
            )
        )
    points.sort(key=lambda point: (point.as_of, point.run_id))
    return points


def _parse(body: str | None) -> dict | None:
    if body is None:
        return None
    try:
        snapshot = json.loads(body)
    except ValueError:
        return None
    return snapshot if isinstance(snapshot, dict) else None


def _team_block(team_id: str, snapshot: dict) -> dict | None:
    teams = snapshot.get("teams")
    if not isinstance(teams, list):
        return None
    return next((team for team in teams if isinstance(team, dict) and team.get("team_id") == team_id), None)


def _market_value(markets: dict, block: str, team_id: str) -> float | None:
    probs = markets.get(block)
    if not isinstance(probs, dict):
        return None
    value = probs.get(team_id)
    return float(value) if isinstance(value, (int, float)) else None
