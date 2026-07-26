"""Raw odds archive; the closing-line record cannot be re-bought, so payloads are stored verbatim."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel

from wolves import ENGINE_VERSION
from wolves.clients.odds.client import TheOddsApiClient
from wolves.clients.odds.contracts import CreditUsage, RawOddsResponse
from wolves.clients.odds.polymarket import GammaPolymarketClient
from wolves.config import Settings
from wolves.markets.series import point_from_snapshot
from wolves.observability.logging import configure_cli_logging
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.layout import ODDS_SERIES_POINT, ODDS_SNAPSHOT
from wolves.sim.format import load_format

logger = logging.getLogger(__name__)


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


def archive_parts(now: datetime) -> dict[str, str]:
    # Second granularity so a scheduler misfire cannot clobber an earlier snapshot.
    return {"date": f"{now:%Y-%m-%d}", "time": f"{now:%H%M%S}"}


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
    """Capture one snapshot and store it wherever storage is configured."""
    now = now or datetime.now(UTC)
    snapshot = await capture_sources(odds=odds, polymarket=polymarket, now=now)
    store = ArtifactStore(settings)
    parts = archive_parts(now)
    key = store.put(ODDS_SNAPSHOT, snapshot.model_dump_json(), **parts)
    logger.info("archived %s (mode=%s)", key, store.mode)

    # Series derivation must never block raw archiving; rebuild_series can backfill.
    try:
        point = point_from_snapshot(snapshot.model_dump(), load_format(settings.data_dir))
        store.put(ODDS_SERIES_POINT, point.model_dump_json(), **parts)
    except Exception:
        logger.warning("series point derivation failed for %s; raw snapshot kept", key, exc_info=True)
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
    parser = argparse.ArgumentParser(description="Archive one raw odds snapshot")
    add_storage_argument(parser)
    args = parser.parse_args()
    asyncio.run(_run(apply_storage_choice(Settings(), args.storage)))


if __name__ == "__main__":
    main()
