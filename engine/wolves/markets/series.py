"""The market time series: each raw archive snapshot parsed once into a
compact append-only series.jsonl of de-vigged consensus probabilities. Raw
payloads stay the source of truth; the series is what the agent queries, the
backend serves and a rebuild can always regenerate."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wolves.clients.odds.contracts import OddsEvent
from wolves.clients.odds.markets import event_consensus
from wolves.clients.odds.polymarket import markets_from_events, winner_probabilities
from wolves.clients.odds.team_names import team_id_for_name
from wolves.sim.format import FormatData

logger = logging.getLogger(__name__)

SERIES_FILENAME = "series.jsonl"


class MatchPoint(BaseModel):
    home: str
    away: str
    commence_at: str
    p_home: float
    p_draw: float
    p_away: float


class SeriesPoint(BaseModel):
    captured_at: str
    outright_bookmakers: dict[str, float]
    outright_polymarket: dict[str, float]
    matches: list[MatchPoint]


def point_from_snapshot(snapshot: dict[str, Any], fmt: FormatData) -> SeriesPoint:
    teams = list(fmt.teams)
    sources = snapshot.get("sources", {})

    bookmakers: dict[str, float] = {}
    for item in (sources.get("odds_outrights") or {}).get("payload") or []:
        event = OddsEvent.model_validate(item)
        for name, prob in event_consensus(event, market_key="outrights").items():
            team_id = team_id_for_name(name, teams)
            if team_id is not None:
                bookmakers[team_id] = prob
    total = sum(bookmakers.values())
    if total > 0:
        bookmakers = {team: round(prob / total, 4) for team, prob in bookmakers.items()}

    polymarket_payload = (sources.get("polymarket") or {}).get("payload") or []
    polymarket = {
        team: round(prob, 4)
        for team, prob in winner_probabilities(markets_from_events(polymarket_payload), teams).items()
    }

    matches: list[MatchPoint] = []
    for item in (sources.get("odds_h2h") or {}).get("payload") or []:
        event = OddsEvent.model_validate(item)
        consensus = event_consensus(event, market_key="h2h")
        if not consensus or event.home_team is None or event.away_team is None:
            continue
        home = team_id_for_name(event.home_team, teams)
        away = team_id_for_name(event.away_team, teams)
        if home is None or away is None:
            continue
        matches.append(
            MatchPoint(
                home=home,
                away=away,
                commence_at=event.commence_time.isoformat() if event.commence_time else "",
                p_home=round(consensus.get(event.home_team, 0.0), 4),
                p_draw=round(consensus.get("Draw", 0.0), 4),
                p_away=round(consensus.get(event.away_team, 0.0), 4),
            )
        )
    return SeriesPoint(
        captured_at=snapshot["captured_at"],
        outright_bookmakers=bookmakers,
        outright_polymarket=polymarket,
        matches=matches,
    )


def append_point(series_path: Path, point: SeriesPoint) -> None:
    series_path.parent.mkdir(parents=True, exist_ok=True)
    with series_path.open("a", encoding="utf-8") as handle:
        handle.write(point.model_dump_json() + "\n")


def load_series(series_path: Path) -> list[SeriesPoint]:
    if not series_path.exists():
        return []
    points = [SeriesPoint.model_validate_json(line) for line in series_path.read_text(encoding="utf-8").splitlines()]
    return sorted(points, key=lambda p: p.captured_at)


def rebuild_series(archive_dir: Path, fmt: FormatData) -> list[SeriesPoint]:
    """Regenerate the whole series from the raw snapshots and rewrite the file."""
    points = []
    for path in sorted(archive_dir.glob("*/*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot.get("sources"):
            points.append(point_from_snapshot(snapshot, fmt))
    points.sort(key=lambda p: p.captured_at)
    series_path = archive_dir / SERIES_FILENAME
    series_path.parent.mkdir(parents=True, exist_ok=True)
    series_path.write_text("".join(p.model_dump_json() + "\n" for p in points), encoding="utf-8")
    logger.info("rebuilt market series: %d points", len(points))
    return points
