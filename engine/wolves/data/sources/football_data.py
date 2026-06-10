"""football-data.co.uk internationals workbook: per-bookmaker 1X2 tournament odds."""

from __future__ import annotations

import io
import math
from datetime import date, datetime

import httpx
import pandas as pd

from wolves.connectors._http import _raise_for_status, async_retrying
from wolves.data.contracts import MatchOddsRecord
from wolves.data.teams import team_key

WORKBOOK_URL = "https://www.football-data.co.uk/internationals.xlsx"
# The server rejects default client agents with a 300 response.
_HEADERS = {"User-Agent": "Mozilla/5.0"}


async def fetch_workbook(*, client: httpx.AsyncClient) -> bytes:
    async for attempt in async_retrying():
        with attempt:
            response = await client.get(WORKBOOK_URL, headers=_HEADERS)
            _raise_for_status(response)
            return response.content
    raise AssertionError("unreachable")


def _bookmaker_trios(columns: list[str]) -> list[tuple[str, str, str, str]]:
    """1X2 column trios as (bookmaker, home, draw, away).

    Most sheets repeat the bookmaker name across three columns, which pandas
    deduplicates to name/.1/.2; the 2018 sheet names its trios explicitly."""
    trios = [
        (name, name, f"{name}.1", f"{name}.2")
        for name in columns
        if f"{name}.1" in columns and f"{name}.2" in columns
    ]
    named = [
        ("Pinnacle", "Pinny-H", "Pinny-D", "Pinny-A"),
        ("market-max", "H-Max", "D-Max", "A-Max"),
        ("market-average", "H-Avg", "D-Avg", "A-Avg"),
    ]
    trios.extend(trio for trio in named if all(column in columns for column in trio[1:]))
    return trios


def _as_price(value: object) -> float | None:
    try:
        price = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 1.0 else None


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def parse_workbook(content: bytes) -> list[MatchOddsRecord]:
    """One record per match per bookmaker with a complete finite 1X2 trio."""
    records: list[MatchOddsRecord] = []
    workbook = pd.ExcelFile(io.BytesIO(content))
    for sheet in workbook.sheet_names:
        frame = workbook.parse(sheet)
        required = {"Competition", "Home", "Away", "Date", "HGFT", "AGFT"}
        if not required.issubset(frame.columns):
            continue
        bookmakers = _bookmaker_trios(list(frame.columns))
        for row in frame.itertuples(index=False):
            row_map = dict(zip(frame.columns, row, strict=True))
            played = _as_date(row_map["Date"])
            if played is None or pd.isna(row_map["HGFT"]) or pd.isna(row_map["AGFT"]):
                continue
            for bookmaker, home_col, draw_col, away_col in bookmakers:
                home = _as_price(row_map[home_col])
                draw = _as_price(row_map[draw_col])
                away = _as_price(row_map[away_col])
                if home is None or draw is None or away is None:
                    continue
                records.append(
                    MatchOddsRecord(
                        competition=str(row_map["Competition"]),
                        date=played,
                        home_team=team_key(str(row_map["Home"])),
                        away_team=team_key(str(row_map["Away"])),
                        home_goals=int(row_map["HGFT"]),
                        away_goals=int(row_map["AGFT"]),
                        bookmaker=bookmaker,
                        home_price=home,
                        draw_price=draw,
                        away_price=away,
                    )
                )
    return records
