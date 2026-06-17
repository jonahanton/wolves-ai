"""Stream tracker: per-run champion-probability bands for tracked teams,
scored for band revision coverage and movement versus stated uncertainty."""

from __future__ import annotations

import math

from pydantic import BaseModel

from wolves.config import Settings
from wolves.snapshot import Snapshot, run_day

# An 80 percent normal band spans 2 x 1.2816 standard deviations.
_NORMAL_80_BAND_SDS = 2.563
_Q_LO = 0.1
_Q_HI = 0.9
_TOP_TEAM_COUNT = 8
_COVERAGE_FLOOR = 0.6
_WIDEN_FACTOR = 1.25


class StreamRecord(BaseModel):
    run_id: str
    as_of: str
    team: str
    mean: float
    q10: float | None = None
    q90: float | None = None


class MovementStats(BaseModel):
    movement_pp: float
    implied_movement_pp: float
    ratio: float


def _settled_teams(snapshot: Snapshot) -> set[str]:
    if snapshot.distributions is None:
        return set()
    return {team for team, dist in snapshot.distributions.teams.items() if "champion" in dist.settled}


def tracked_teams(snapshot: Snapshot) -> list[str]:
    """Focus team plus the top teams by champion probability, open teams only;
    a settled team leaves the set and the next-largest open team enters."""
    settled = _settled_teams(snapshot)
    by_prob = sorted(
        (t for t in snapshot.teams if t.team_id not in settled),
        key=lambda t: t.champion_prob,
        reverse=True,
    )
    tracked = [t.team_id for t in by_prob[:_TOP_TEAM_COUNT]]
    focus = snapshot.focus.team_id
    if focus not in tracked and focus not in settled and any(t.team_id == focus for t in snapshot.teams):
        tracked.insert(0, focus)
    return tracked


def _band(snapshot: Snapshot, team: str) -> tuple[float | None, float | None]:
    block = snapshot.distributions
    if block is None or _Q_LO not in block.quantile_levels or _Q_HI not in block.quantile_levels:
        return None, None
    dist = block.teams.get(team)
    if dist is None or "champion" not in dist.quantiles:
        return None, None
    quantiles = dist.quantiles["champion"]
    return quantiles[block.quantile_levels.index(_Q_LO)], quantiles[block.quantile_levels.index(_Q_HI)]


def stream_records(snapshot: Snapshot) -> list[StreamRecord]:
    """One record per tracked team for this run."""
    means = {t.team_id: t.champion_prob for t in snapshot.teams}
    records: list[StreamRecord] = []
    for team in tracked_teams(snapshot):
        q10, q90 = _band(snapshot, team)
        records.append(
            StreamRecord(
                run_id=snapshot.run.run_id,
                as_of=run_day(snapshot.run),
                team=team,
                mean=means[team],
                q10=q10,
                q90=q90,
            )
        )
    return records


def load_stream(settings: Settings) -> list[StreamRecord]:
    path = settings.stream_path
    if not path.exists():
        return []
    return [
        StreamRecord.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def record_stream(settings: Settings, snapshot: Snapshot) -> None:
    """Append this run's tracked-team records to the stream; idempotent per run."""
    existing = load_stream(settings)
    if any(r.run_id == snapshot.run.run_id for r in existing):
        return
    path = settings.stream_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in stream_records(snapshot):
            handle.write(record.model_dump_json() + "\n")


def _consecutive_pairs(records: list[StreamRecord]) -> list[tuple[StreamRecord, StreamRecord]]:
    by_team: dict[str, list[StreamRecord]] = {}
    for record in records:
        by_team.setdefault(record.team, []).append(record)
    return [(seq[i], seq[i + 1]) for seq in by_team.values() for i in range(len(seq) - 1)]


def _scored_pairs(records: list[StreamRecord]) -> list[tuple[StreamRecord, StreamRecord]]:
    return [(a, b) for a, b in _consecutive_pairs(records) if a.q10 is not None and a.q90 is not None]


def band_coverage(records: list[StreamRecord]) -> float | None:
    """Fraction of consecutive same-team pairs where the next mean lands
    inside the previous 80 percent band; healthy is around 0.8."""
    pairs = _scored_pairs(records)
    if not pairs:
        return None
    inside = sum(1 for a, b in pairs if a.q10 <= b.mean <= a.q90)  # type: ignore[operator]
    return inside / len(pairs)


def movement_stats(records: list[StreamRecord]) -> MovementStats | None:
    """Realised mean movement against the movement the bands imply.

    The band is the variance proxy: var_t = ((q90 - q10) / 2.563)^2, the
    normal-band conversion. Treating each run's stated variance as the
    expected one-step squared movement is a simplification of the
    Augenblick-Rabin martingale test: it ignores how variance should drain
    over the remaining horizon, but the ratio still reads cleanly. Above 1
    means overreaction or too-narrow bands; below 1 stickiness or too-wide."""
    pairs = _scored_pairs(records)
    if not pairs:
        return None
    moves = [(b.mean - a.mean) ** 2 for a, b in pairs]
    variances = [((a.q90 - a.q10) / _NORMAL_80_BAND_SDS) ** 2 for a, _ in pairs]  # type: ignore[operator]
    movement_pp = math.sqrt(sum(moves) / len(moves)) * 100.0
    implied_pp = math.sqrt(sum(variances) / len(variances)) * 100.0
    ratio = movement_pp / implied_pp if implied_pp > 0.0 else float("inf")
    return MovementStats(movement_pp=movement_pp, implied_movement_pp=implied_pp, ratio=ratio)


def dispersion_scale(records: list[StreamRecord], *, min_n: int) -> float:
    """Bounded band-widening factor: widen when trailing coverage is
    materially below the 0.8 owed, never narrow when coverage is high."""
    pairs = _scored_pairs(records)
    if len(pairs) < min_n:
        return 1.0
    coverage = band_coverage(records)
    if coverage is not None and coverage < _COVERAGE_FLOOR:
        return _WIDEN_FACTOR
    return 1.0
