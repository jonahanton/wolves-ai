"""WC2022 closing odds pulled from The Odds API historical endpoint by
scripts/pull_wc2022_closes.py. Each h2h snapshot was taken minutes before one
kickoff cluster, so only events commencing shortly after the snapshot carry
closing prices; later events appear too but at non-closing prices."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wolves.data.prices import valid_price
from wolves.data.teams import canonical_team_key

logger = logging.getLogger(__name__)

CLOSING_WINDOW = timedelta(minutes=30)


class ClosingOddsRecord(BaseModel):
    snapshot_at: datetime
    commence_at: datetime
    home_team: str
    away_team: str
    bookmaker: str
    home_price: float
    draw_price: float
    away_price: float


class OutrightCloseRecord(BaseModel):
    snapshot_at: datetime
    bookmaker: str
    team: str
    price: float


def _h2h_records(snapshot: dict[str, Any]) -> list[ClosingOddsRecord]:
    snapshot_at = datetime.fromisoformat(snapshot["timestamp"])
    records: list[ClosingOddsRecord] = []
    for event in snapshot["data"]:
        commence_at = datetime.fromisoformat(event["commence_time"])
        if not timedelta(0) <= commence_at - snapshot_at <= CLOSING_WINDOW:
            continue
        home, away = event["home_team"], event["away_team"]
        for bookmaker in event["bookmakers"]:
            markets = {market["key"]: market for market in bookmaker["markets"]}
            if "h2h" not in markets:
                continue
            prices = {
                outcome["name"]: price
                for outcome in markets["h2h"]["outcomes"]
                if (price := valid_price(outcome["price"])) is not None
            }
            if not {home, away, "Draw"} <= prices.keys():
                logger.warning(
                    "dropping incomplete or invalid h2h trio from %s for %s v %s", bookmaker["key"], home, away
                )
                continue
            records.append(
                ClosingOddsRecord(
                    snapshot_at=snapshot_at,
                    commence_at=commence_at,
                    home_team=canonical_team_key(home),
                    away_team=canonical_team_key(away),
                    bookmaker=bookmaker["key"],
                    home_price=prices[home],
                    draw_price=prices["Draw"],
                    away_price=prices[away],
                )
            )
    return records


def _outright_records(snapshot: dict[str, Any]) -> list[OutrightCloseRecord]:
    snapshot_at = datetime.fromisoformat(snapshot["timestamp"])
    return [
        OutrightCloseRecord(
            snapshot_at=snapshot_at,
            bookmaker=bookmaker["key"],
            team=canonical_team_key(outcome["name"]),
            price=price,
        )
        for event in snapshot["data"]
        for bookmaker in event["bookmakers"]
        for market in bookmaker["markets"]
        if market["key"] == "outrights"
        for outcome in market["outcomes"]
        if (price := valid_price(outcome["price"])) is not None
    ]


def load_closes(odds_dir: Path) -> tuple[list[ClosingOddsRecord], list[OutrightCloseRecord]]:
    """Parse every pulled snapshot; absent directory means no closes on this machine."""
    if not odds_dir.exists():
        logger.warning("%s absent; wc2022 close tables will be empty", odds_dir)
        return [], []
    closes: list[ClosingOddsRecord] = []
    outrights: list[OutrightCloseRecord] = []
    for path in sorted(odds_dir.glob("*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if path.name.startswith("outrights"):
            outrights.extend(_outright_records(snapshot))
        else:
            closes.extend(_h2h_records(snapshot))
    return closes, outrights
