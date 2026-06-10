"""Raw odds archive: one snapshot per invocation, stored exactly as the APIs
returned it. The 2026 closing-line record cannot be bought later, so nothing
is parsed or de-vigged here; that happens downstream at read time. The
scheduler owns the cadence (cron locally, EventBridge in production)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from wolves import ENGINE_VERSION
from wolves.clients.odds.client import TheOddsApiClient
from wolves.clients.odds.contracts import CreditUsage, RawOddsResponse
from wolves.clients.odds.polymarket import GammaPolymarketClient
from wolves.clients.s3.client import S3Client
from wolves.config import Settings
from wolves.markets.series import point_from_snapshot, point_path, write_point
from wolves.observability.logging import configure_cli_logging
from wolves.sim.format import load_format

logger = logging.getLogger(__name__)

S3_PREFIX = "odds-archive"


class AllSourcesFailedError(Exception):
    """Every archive source failed; there is nothing worth storing."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__(f"all archive sources failed: {errors}")


class RawOddsSource(Protocol):
    async def outrights_raw(self) -> RawOddsResponse: ...
    async def h2h_raw(self) -> RawOddsResponse: ...


class RawEventsSource(Protocol):
    async def winner_events(self) -> list[dict[str, Any]]: ...


class SourceCapture(BaseModel):
    payload: Any = None
    credits: CreditUsage | None = None
    error: str | None = None


class ArchiveSnapshot(BaseModel):
    captured_at: str
    engine_version: str
    sources: dict[str, SourceCapture]


def archive_key(now: datetime) -> str:
    # Second granularity so a scheduler misfire cannot clobber an earlier snapshot.
    return f"{now:%Y-%m-%d}/{now:%H%M%S}.json"


async def capture_sources(*, odds: RawOddsSource, polymarket: RawEventsSource, now: datetime) -> ArchiveSnapshot:
    """Fetch every source, recording failures per source; raise only when all fail."""

    async def odds_capture(fetch: Callable[[], Awaitable[RawOddsResponse]]) -> SourceCapture:
        raw = await fetch()
        return SourceCapture(payload=raw.payload, credits=raw.credits)

    async def polymarket_capture() -> SourceCapture:
        return SourceCapture(payload=await polymarket.winner_events())

    sources: dict[str, SourceCapture] = {}
    captures = {
        "odds_outrights": lambda: odds_capture(odds.outrights_raw),
        "odds_h2h": lambda: odds_capture(odds.h2h_raw),
        "polymarket": polymarket_capture,
    }
    for name, capture in captures.items():
        # Fault-isolation boundary: one source going down must not lose the others' snapshot.
        try:
            sources[name] = await capture()
        except Exception as exc:
            logger.warning("archive source %s failed: %s", name, exc)
            sources[name] = SourceCapture(error=f"{type(exc).__name__}: {exc}")

    errors = {name: capture.error for name, capture in sources.items() if capture.error is not None}
    if len(errors) == len(sources):
        raise AllSourcesFailedError(errors)
    return ArchiveSnapshot(
        captured_at=now.isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
        sources=sources,
    )


async def archive_pass(
    settings: Settings,
    *,
    odds: RawOddsSource,
    polymarket: RawEventsSource,
    now: datetime | None = None,
) -> str:
    """Capture one snapshot, write it locally and to S3; return the archive key."""
    now = now or datetime.now(UTC)
    snapshot = await capture_sources(odds=odds, polymarket=polymarket, now=now)
    key = archive_key(now)
    body = snapshot.model_dump_json()

    local_path = settings.runs_root / "odds-archive" / key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(body, encoding="utf-8")
    logger.info("archived %s locally (%d bytes)", key, len(body))

    # Series derivation must never block raw archiving; rebuild_series can backfill.
    series_file: Path | None = None
    try:
        point = point_from_snapshot(snapshot.model_dump(), load_format(settings.data_dir))
        series_file = write_point(local_path, point)
    except Exception:
        logger.warning("series point derivation failed for %s; raw snapshot kept", key, exc_info=True)

    # Local write happens first so an S3 outage is loud without losing the snapshot.
    if settings.agent_state_bucket:
        s3 = S3Client(bucket=settings.agent_state_bucket, region=settings.aws_region)
        s3.put_text(f"{S3_PREFIX}/{key}", body, content_type="application/json")
        if series_file is not None:
            series_key = str(point_path(Path(key)))
            s3.put_text(
                f"{S3_PREFIX}/{series_key}", series_file.read_text(encoding="utf-8"), content_type="application/json"
            )
        logger.info("archived %s to s3://%s/%s/%s", key, settings.agent_state_bucket, S3_PREFIX, key)
    else:
        logger.info("agent_state_bucket unset; snapshot kept locally only")
    return key


async def _run(settings: Settings) -> None:
    odds = TheOddsApiClient(settings.odds_api_key)
    polymarket = GammaPolymarketClient()
    try:
        await archive_pass(settings, odds=odds, polymarket=polymarket)
    finally:
        await odds.aclose()
        await polymarket.aclose()


def main() -> None:
    configure_cli_logging()
    asyncio.run(_run(Settings()))


if __name__ == "__main__":
    main()
