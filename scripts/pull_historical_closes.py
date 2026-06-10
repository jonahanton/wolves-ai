"""Pull closing odds for every tournament in the closes registry from The
Odds API historical endpoint (10 paid credits per snapshot). Raw snapshots
live in the gitignored data/odds/<slug>/ and mirror to S3 when a bucket is
configured. Idempotent: existing files are never re-fetched.

Run from the repo root: uv run --project engine python scripts/pull_historical_closes.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from wolves.clients.s3.client import S3Client
from wolves.config import Settings
from wolves.data.tournaments import CLOSES_TOURNAMENTS, ClosesTournament
from wolves.observability.logging import configure_cli_logging

logger = logging.getLogger("pull_historical_closes")

ODDS_DIR = Path(__file__).resolve().parents[1] / "data" / "odds"
FIXTURES_URL = "https://v3.football.api-sports.io/fixtures"
HISTORICAL_URL = "https://api.the-odds-api.com/v4/historical/sports/{sport}/odds"
CLOSE_OFFSET = timedelta(minutes=5)


async def kickoffs(settings: Settings, tournament: ClosesTournament, *, client: httpx.AsyncClient) -> list[datetime]:
    response = await client.get(
        FIXTURES_URL,
        params={"league": tournament.api_football_league, "season": tournament.api_football_season},
        headers={"x-apisports-key": settings.api_football_key},
    )
    response.raise_for_status()
    fixtures = response.json()["response"]
    # The season fixture list includes qualifiers; only finals-window kickoffs have closes.
    window = (tournament.first_match, tournament.last_match)
    times = {
        kickoff
        for item in fixtures
        if window[0] <= (kickoff := datetime.fromisoformat(item["fixture"]["date"]).astimezone(UTC)).date() <= window[1]
    }
    logger.info("%s: %d fixtures, %d distinct kickoffs", tournament.slug, len(fixtures), len(times))
    return sorted(times)


async def pull_snapshot(
    settings: Settings, *, client: httpx.AsyncClient, sport: str, at: datetime, out_path: Path
) -> bool:
    if out_path.exists():
        return False
    response = await client.get(
        HISTORICAL_URL.format(sport=sport),
        params={
            "apiKey": settings.odds_api_key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
            "date": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    response.raise_for_status()
    out_path.write_text(json.dumps(response.json()), encoding="utf-8")
    logger.info("pulled %s/%s (credits remaining %s)", out_path.parent.name, out_path.name, response.headers.get("x-requests-remaining"))
    return True


def mirror_to_s3(settings: Settings) -> None:
    if not settings.agent_state_bucket:
        logger.warning("agent_state_bucket unset; snapshots exist on this machine only")
        return
    s3 = S3Client(bucket=settings.agent_state_bucket, region=settings.aws_region)
    existing = set(s3.list_keys(prefix="odds-archive/closes/"))
    for path in sorted(ODDS_DIR.glob("*/*.json")):
        key = f"odds-archive/closes/{path.parent.name}/{path.name}"
        if key not in existing:
            s3.put_text(key, path.read_text(encoding="utf-8"), content_type="application/json")
            logger.info("mirrored %s", key)


async def main() -> None:
    configure_cli_logging()
    settings = Settings()
    pulled = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for tournament in CLOSES_TOURNAMENTS:
            out_dir = ODDS_DIR / tournament.slug
            out_dir.mkdir(parents=True, exist_ok=True)
            for kickoff in await kickoffs(settings, tournament, client=client):
                at = kickoff - CLOSE_OFFSET
                pulled += await pull_snapshot(
                    settings,
                    client=client,
                    sport=tournament.odds_sport_key,
                    at=at,
                    out_path=out_dir / f"h2h-{at:%Y%m%dT%H%M}Z.json",
                )
    logger.info("done: %d new snapshot(s)", pulled)
    mirror_to_s3(settings)


if __name__ == "__main__":
    asyncio.run(main())
