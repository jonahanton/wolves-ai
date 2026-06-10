"""One-off acquisition of WC2022 closing odds from The Odds API historical
endpoint (paid credits: 10 per snapshot). Raw snapshots live in the gitignored
data/odds/wc2022/ and are mirrored to S3 when a bucket is configured, because
re-pulling them costs real money. Idempotent: existing files are never
re-fetched, and the S3 mirror runs on every invocation.

Run from the repo root: uv run --project engine python scripts/pull_wc2022_closes.py
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
from wolves.observability.logging import configure_cli_logging

logger = logging.getLogger("pull_wc2022_closes")

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "odds" / "wc2022"
FIXTURES_URL = "https://v3.football.api-sports.io/fixtures"
HISTORICAL_URL = "https://api.the-odds-api.com/v4/historical/sports/{sport}/odds"
# Snapshot taken five minutes before kickoff approximates the closing line.
CLOSE_OFFSET = timedelta(minutes=5)
OUTRIGHT_CLOSE = datetime(2022, 11, 20, 15, 55, tzinfo=UTC)


async def wc2022_kickoffs(settings: Settings, *, client: httpx.AsyncClient) -> list[datetime]:
    response = await client.get(
        FIXTURES_URL,
        params={"league": 1, "season": 2022},
        headers={"x-apisports-key": settings.api_football_key},
    )
    response.raise_for_status()
    fixtures = response.json()["response"]
    kickoffs = {datetime.fromisoformat(item["fixture"]["date"]).astimezone(UTC) for item in fixtures}
    logger.info("%d fixtures, %d distinct kickoffs", len(fixtures), len(kickoffs))
    return sorted(kickoffs)


async def pull_snapshot(
    settings: Settings, *, client: httpx.AsyncClient, sport: str, markets: str, at: datetime, out_path: Path
) -> bool:
    if out_path.exists():
        logger.info("skip %s (already pulled)", out_path.name)
        return False
    response = await client.get(
        HISTORICAL_URL.format(sport=sport),
        params={
            "apiKey": settings.odds_api_key,
            "regions": "eu",
            "markets": markets,
            "oddsFormat": "decimal",
            "date": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    response.raise_for_status()
    out_path.write_text(json.dumps(response.json()), encoding="utf-8")
    logger.info("pulled %s (credits remaining %s)", out_path.name, response.headers.get("x-requests-remaining"))
    return True


async def main() -> None:
    configure_cli_logging()
    settings = Settings()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30.0) as client:
        kickoffs = await wc2022_kickoffs(settings, client=client)
        pulled = await pull_snapshot(
            settings,
            client=client,
            sport="soccer_fifa_world_cup_winner",
            markets="outrights",
            at=OUTRIGHT_CLOSE,
            out_path=OUT_DIR / "outrights-close.json",
        )
        for kickoff in kickoffs:
            at = kickoff - CLOSE_OFFSET
            pulled += await pull_snapshot(
                settings,
                client=client,
                sport="soccer_fifa_world_cup",
                markets="h2h",
                at=at,
                out_path=OUT_DIR / f"h2h-{at:%Y%m%dT%H%M}Z.json",
            )
    logger.info("done: %d new snapshot(s)", pulled)
    mirror_to_s3(settings)


def mirror_to_s3(settings: Settings) -> None:
    if not settings.agent_state_bucket:
        logger.warning("agent_state_bucket unset; snapshots exist on this machine only")
        return
    s3 = S3Client(bucket=settings.agent_state_bucket, region=settings.aws_region)
    existing = set(s3.list_keys(prefix="odds-archive/wc2022/"))
    for path in sorted(OUT_DIR.glob("*.json")):
        key = f"odds-archive/wc2022/{path.name}"
        if key not in existing:
            s3.put_text(key, path.read_text(encoding="utf-8"), content_type="application/json")
            logger.info("mirrored %s", key)


if __name__ == "__main__":
    asyncio.run(main())
