from __future__ import annotations

from pydantic import BaseModel, Field

from wolves.snapshot import Snapshot

MIN_DELTA = 0.005


class SlotDelta(BaseModel):
    match: int
    side: str
    team_id: str
    delta: float


class SnapshotDiff(BaseModel):
    finish_deltas: dict[str, float]
    reach_deltas: dict[str, float]
    champion_deltas: dict[str, float] = Field(default_factory=dict)
    slot_deltas: list[SlotDelta] = Field(default_factory=list)


def _delta_map(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = set(before) | set(after)
    return {k: round(after.get(k, 0.0) - before.get(k, 0.0), 4) for k in sorted(keys)}


def diff_snapshots(before: Snapshot, after: Snapshot, *, min_delta: float = MIN_DELTA) -> SnapshotDiff:
    """Probabilities that moved between two runs; small slot moves are filtered out."""
    champion_before = {t.team_id: t.champion_prob for t in before.teams}
    champion_after = {t.team_id: t.champion_prob for t in after.teams}
    champion_deltas = {k: v for k, v in _delta_map(champion_before, champion_after).items() if abs(v) >= min_delta}

    slots_before = {s.match: s for s in before.slots}
    slot_deltas: list[SlotDelta] = []
    for slot in after.slots:
        prev = slots_before.get(slot.match)
        if prev is None:
            continue
        for side in ("home", "away"):
            now = {c.team_id: c.prob for c in getattr(slot, side).candidates}
            was = {c.team_id: c.prob for c in getattr(prev, side).candidates}
            for team_id, delta in _delta_map(was, now).items():
                if abs(delta) >= min_delta:
                    slot_deltas.append(SlotDelta(match=slot.match, side=side, team_id=team_id, delta=delta))

    return SnapshotDiff(
        finish_deltas=_delta_map(before.focus.finish_probs, after.focus.finish_probs),
        reach_deltas=_delta_map(before.focus.reach_probs, after.focus.reach_probs),
        champion_deltas=champion_deltas,
        slot_deltas=slot_deltas,
    )
