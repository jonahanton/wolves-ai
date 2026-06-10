"""martj42/international_results (CC0): the results backbone for fitting."""

from __future__ import annotations

import csv
import io
from datetime import date

import httpx

from wolves.connectors._http import _raise_for_status, async_retrying
from wolves.data.contracts import MatchRecord, ShootoutRecord
from wolves.data.importance import importance_weight
from wolves.data.teams import team_key

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
SHOOTOUTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"


async def fetch(url: str, *, client: httpx.AsyncClient) -> str:
    async for attempt in async_retrying():
        with attempt:
            response = await client.get(url)
            _raise_for_status(response)
            return response.text
    raise AssertionError("unreachable")


def parse_results(text: str) -> list[MatchRecord]:
    records: list[MatchRecord] = []
    seen: set[tuple] = set()
    for row in csv.DictReader(io.StringIO(text)):
        # Scheduled-but-unplayed fixtures appear with NA scores at the tail of the file.
        if row["home_score"] in ("", "NA"):
            continue
        # The upstream file occasionally carries an exact duplicate row.
        key = (row["date"], row["home_team"], row["away_team"], row["home_score"], row["away_score"])
        if key in seen:
            continue
        seen.add(key)
        records.append(
            MatchRecord(
                date=date.fromisoformat(row["date"]),
                home_team=team_key(row["home_team"]),
                away_team=team_key(row["away_team"]),
                home_goals=int(row["home_score"]),
                away_goals=int(row["away_score"]),
                tournament=row["tournament"],
                importance=importance_weight(row["tournament"]),
                neutral=row["neutral"].upper() == "TRUE",
            )
        )
    return records


def parse_shootouts(text: str) -> list[ShootoutRecord]:
    return [
        ShootoutRecord(
            date=date.fromisoformat(row["date"]),
            home_team=team_key(row["home_team"]),
            away_team=team_key(row["away_team"]),
            winner=team_key(row["winner"]),
        )
        for row in csv.DictReader(io.StringIO(text))
        if row["winner"]
    ]
