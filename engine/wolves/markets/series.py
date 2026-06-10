"""Market series points, one per raw snapshot; raw payloads stay the source of truth."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wolves.clients.odds.contracts import OddsEvent
from wolves.clients.odds.markets import event_consensus, market_last_updates
from wolves.clients.odds.polymarket import markets_from_events, winner_probabilities
from wolves.clients.odds.team_names import team_id_for_name
from wolves.sim.format import FormatData

logger = logging.getLogger(__name__)

SERIES_SUFFIX = ".series.json"


class MatchPoint(BaseModel):
    home: str
    away: str
    commence_at: str
    p_home: float
    p_draw: float
    p_away: float
    last_update: str | None = None


class SeriesPoint(BaseModel):
    captured_at: str
    outright_bookmakers: dict[str, float]
    outright_polymarket: dict[str, float]
    matches: list[MatchPoint]
    outright_updated_oldest: str | None = None
    outright_updated_newest: str | None = None


def point_from_snapshot(snapshot: dict[str, Any], fmt: FormatData) -> SeriesPoint:
    teams = list(fmt.teams)
    sources = snapshot.get("sources", {})

    bookmakers: dict[str, float] = {}
    outright_updates = []
    for item in (sources.get("odds_outrights") or {}).get("payload") or []:
        event = OddsEvent.model_validate(item)
        outright_updates.extend(market_last_updates(event, market_key="outrights"))
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
        updated = max(market_last_updates(event, market_key="h2h"), default=None)
        matches.append(
            MatchPoint(
                home=home,
                away=away,
                commence_at=event.commence_time.isoformat() if event.commence_time else "",
                p_home=round(consensus.get(event.home_team, 0.0), 4),
                p_draw=round(consensus.get("Draw", 0.0), 4),
                p_away=round(consensus.get(event.away_team, 0.0), 4),
                last_update=updated.isoformat() if updated else None,
            )
        )
    return SeriesPoint(
        captured_at=snapshot["captured_at"],
        outright_bookmakers=bookmakers,
        outright_polymarket=polymarket,
        matches=matches,
        outright_updated_oldest=min(outright_updates).isoformat() if outright_updates else None,
        outright_updated_newest=max(outright_updates).isoformat() if outright_updates else None,
    )


def point_path(raw_path: Path) -> Path:
    # with_suffix rejects compound suffixes on older Pythons; compose by name.
    return raw_path.with_name(raw_path.stem + SERIES_SUFFIX)


def write_point(raw_path: Path, point: SeriesPoint) -> Path:
    destination = point_path(raw_path)
    destination.write_text(point.model_dump_json(), encoding="utf-8")
    return destination


def _raw_paths(archive_dir: Path) -> list[Path]:
    return sorted(p for p in archive_dir.glob("*/*.json") if not p.name.endswith(SERIES_SUFFIX))


def load_series(archive_dir: Path) -> list[SeriesPoint]:
    points = [
        SeriesPoint.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(archive_dir.glob(f"*/*{SERIES_SUFFIX}"))
    ]
    return sorted(points, key=lambda p: p.captured_at)


def rebuild_series(archive_dir: Path, fmt: FormatData) -> list[SeriesPoint]:
    """Regenerate every point file from the raw snapshots."""
    points = []
    for path in _raw_paths(archive_dir):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot.get("sources"):
            point = point_from_snapshot(snapshot, fmt)
            write_point(path, point)
            points.append(point)
    logger.info("rebuilt market series: %d point(s)", len(points))
    return sorted(points, key=lambda p: p.captured_at)


def compact_series(archive_dir: Path) -> Path:
    """Fold the per-snapshot outright series points into one parquet table.

    Derived and rebuildable; raw snapshots stay the source of truth. One row
    per (captured_at, source, team)."""
    import pandas as pd

    rows = [
        {"captured_at": point.captured_at, "source": source, "team": team, "p_title": prob}
        for point in load_series(archive_dir)
        for source, outright in (
            ("bookmakers", point.outright_bookmakers),
            ("polymarket", point.outright_polymarket),
        )
        for team, prob in outright.items()
    ]
    import duckdb

    destination = archive_dir / "market_series.parquet"
    frame = pd.DataFrame(rows, columns=["captured_at", "source", "team", "p_title"])
    con = duckdb.connect()
    try:
        con.register("series", frame)
        # duckdb writes parquet natively, so pandas needs no pyarrow dependency.
        con.execute(f"COPY series TO '{destination.as_posix()}' (FORMAT parquet)")
    finally:
        con.close()
    logger.info("compacted market series: %d row(s)", len(rows))
    return destination
