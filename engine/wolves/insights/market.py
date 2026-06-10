"""Market movement digests over the stored series: bookmaker outrights,
Polymarket and per-match h2h as time series with deltas. Output is capped at
source so a full tournament of snapshots stays a small digest."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from wolves.clients.s3.client import S3Client
from wolves.config import Settings
from wolves.markets.series import SERIES_SUFFIX, SeriesPoint, load_series, rebuild_series
from wolves.sim.format import FormatData

TOP_TEAMS = 20
HISTORY_POINTS = 5


class ProbabilityPoint(BaseModel):
    captured_at: str
    probability: float


class TeamMovement(BaseModel):
    team: str
    current: float
    history: list[ProbabilityPoint]
    delta_pp_vs_previous: float
    delta_pp_vs_oldest: float


class MatchMovement(BaseModel):
    home: str
    away: str
    commence_at: str
    current: dict[str, float]
    previous: dict[str, float] | None
    max_move_pp: float


class MarketMovement(BaseModel):
    snapshots: list[str]
    outright_bookmakers: list[TeamMovement]
    outright_polymarket: list[TeamMovement]
    matches: list[MatchMovement]


def _movements(series: list[SeriesPoint], source: str, *, history_points: int) -> list[TeamMovement]:
    history: dict[str, list[ProbabilityPoint]] = {}
    for point in series:
        for team, prob in getattr(point, source).items():
            history.setdefault(team, []).append(ProbabilityPoint(captured_at=point.captured_at, probability=prob))
    movements = []
    for team, points in history.items():
        current = points[-1].probability
        previous = points[-2].probability if len(points) > 1 else current
        movements.append(
            TeamMovement(
                team=team,
                current=current,
                history=points[-history_points:],
                delta_pp_vs_previous=round((current - previous) * 100.0, 2),
                delta_pp_vs_oldest=round((current - points[0].probability) * 100.0, 2),
            )
        )
    ranked = sorted(movements, key=lambda m: (-abs(m.delta_pp_vs_previous), -m.current))
    return sorted(ranked[:TOP_TEAMS], key=lambda m: -m.current)


def _match_movements(series: list[SeriesPoint]) -> list[MatchMovement]:
    by_pair: dict[tuple[str, str, str], list[dict[str, float]]] = {}
    for point in series:
        for match in point.matches:
            probs = {"home": match.p_home, "draw": match.p_draw, "away": match.p_away}
            by_pair.setdefault((match.home, match.away, match.commence_at), []).append(probs)
    movements = []
    for (home, away, commence), points in by_pair.items():
        current, previous = points[-1], points[-2] if len(points) > 1 else None
        max_move = max(abs(current[k] - previous[k]) for k in current) * 100.0 if previous else 0.0
        movements.append(
            MatchMovement(
                home=home,
                away=away,
                commence_at=commence,
                current=current,
                previous=previous,
                max_move_pp=round(max_move, 2),
            )
        )
    return sorted(movements, key=lambda m: m.commence_at)


def market_movement(archive_dir: Path, fmt: FormatData, *, history_points: int = HISTORY_POINTS) -> MarketMovement:
    series = load_series(archive_dir)
    if not series:
        series = rebuild_series(archive_dir, fmt)
    return MarketMovement(
        snapshots=[point.captured_at for point in series],
        outright_bookmakers=_movements(series, "outright_bookmakers", history_points=history_points),
        outright_polymarket=_movements(series, "outright_polymarket", history_points=history_points),
        matches=_match_movements(series),
    )


def sync_series_from_s3(settings: Settings, archive_dir: Path) -> int:
    """Download series points a fresh container does not have; returns new files."""
    if not settings.agent_state_bucket:
        return 0
    s3 = S3Client(bucket=settings.agent_state_bucket, region=settings.aws_region)
    downloaded = 0
    for key in s3.list_keys(prefix="odds-archive/"):
        if not key.endswith(SERIES_SUFFIX):
            continue
        relative = Path(key).relative_to("odds-archive")
        destination = archive_dir / relative
        if destination.exists():
            continue
        body = s3.get_text(key)
        if body is None:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body, encoding="utf-8")
        downloaded += 1
    return downloaded
