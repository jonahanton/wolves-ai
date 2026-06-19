"""In-process homes for the former ECS live and archive tasks; single-writer by design."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from wolves.archive import archive_pass
from wolves.clients.odds.client import TheOddsApiClient
from wolves.clients.odds.polymarket import GammaPolymarketClient
from wolves.forecast import Forecaster
from wolves.live import build_fixtures_client, live_pass, near_kickoff
from wolves.live_state import LiveStateStore
from wolves.s3.artifacts import ArtifactStore
from wolves_backend.impact_report import NoAgentForecastError

if TYPE_CHECKING:
    from wolves.config import Settings as EngineSettings
    from wolves_backend.clients.alerts import Alerts
    from wolves_backend.deps import Deps
    from wolves_backend.sim import EngineService

logger = logging.getLogger(__name__)

FAST_HORIZON = timedelta(hours=1)


def next_archive_time(now: datetime, *, hours: tuple[int, ...]) -> datetime:
    """The next capture instant strictly after now, at one of the UTC hours."""
    for offset in (0, 1):
        day = now.date() + timedelta(days=offset)
        for hour in sorted(hours):
            slot = datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
            if slot > now:
                return slot
    raise ValueError(f"no archive hour after {now}")


class LiveLoop:
    """The wolves.live cadence, in-process: fast near kickoffs, slow when idle."""

    def __init__(self, *, deps: Deps, alerts: Alerts) -> None:
        self._deps = deps
        self._engine = deps.engine
        self._alerts = alerts
        self._settings: EngineSettings = deps.engine.settings
        self._artifacts = ArtifactStore(self._settings)
        self._forecaster: Forecaster | None = None

    async def run(self) -> None:
        while True:
            try:
                published = await self._engine.run_blocking(self._pass)
            except Exception as exc:
                logger.exception("live pass failed; continuing the loop")
                await asyncio.to_thread(self._alerts.publish, "live", f"live pass failed: {exc}")
                published = False
            if published:
                # A result landed: refit next pass, and let routes pick up the new artifact.
                self._forecaster = None
                await self._engine.refresh()
            # The overlay drifts with the match clock, so impact rebuilds every pass.
            await self._refresh_impact()
            await self._idle_wait()

    async def _new_agent_forecast_landed(self) -> bool:
        """A fresh agent snapshot exists that the impact report has not anchored to yet."""
        try:
            refs = await self._deps.snapshots.index_for(datetime.now(UTC).date())
        except Exception:
            logger.warning("agent-snapshot probe failed; deferring to the idle cadence", exc_info=True)
            return False
        newest = next((ref for ref in refs if ref.kind == "agent"), None)
        return newest is not None and newest.run_id != self._deps.impact.anchored_run_id()

    async def _refresh_impact(self) -> None:
        if not self._engine.ready:
            return
        try:
            await self._deps.impact.refresh(self._deps)
        except NoAgentForecastError:
            logger.info("no agent forecast yet; impact refresh skipped")
        except Exception:
            logger.exception("impact refresh failed; serving the previous report")

    def _pass(self) -> bool:
        # live_pass mixes async polling with inline numpy; a worker-thread loop keeps it off the API's.
        return asyncio.run(self._pass_async())

    async def _pass_async(self) -> bool:
        if self._forecaster is None:
            self._forecaster = Forecaster(self._settings)
        fixtures = build_fixtures_client(self._settings)
        try:
            return await live_pass(
                self._settings, fixtures=fixtures, n_sims=self._settings.n_sims, forecaster=self._forecaster
            )
        finally:
            await fixtures.aclose()

    async def _idle_wait(self) -> None:
        """Wait out the interval, but cut it short the moment a fresh agent forecast
        lands so the lip re-anchors within one probe rather than one idle gap."""
        idle = await asyncio.to_thread(self._interval)
        chunk = self._settings.impact_anchor_probe_interval_s
        if idle <= chunk:
            await asyncio.sleep(idle)
            return
        remaining = idle
        while remaining > 0:
            await asyncio.sleep(min(chunk, remaining))
            remaining -= chunk
            if await self._new_agent_forecast_landed():
                return

    def _interval(self) -> float:
        try:
            state = LiveStateStore(self._artifacts).load()
            fast = near_kickoff(state, now=datetime.now(UTC), horizon=FAST_HORIZON)
        except Exception:
            # A transient read failure must not kill the loop; err slow until the next pass.
            logger.warning("interval probe failed; backing off to the idle cadence", exc_info=True)
            return self._settings.live_idle_interval_s
        return self._settings.live_poll_interval_s if fast else self._settings.live_idle_interval_s


class ArchiveLoop:
    """The odds-archive schedule, in-process: one capture at each archive hour."""

    def __init__(self, *, engine: EngineService, alerts: Alerts, hours: tuple[int, ...]) -> None:
        self._engine = engine
        self._settings: EngineSettings = engine.settings
        self._alerts = alerts
        self._hours = hours

    async def run(self) -> None:
        while True:
            now = datetime.now(UTC)
            await asyncio.sleep((next_archive_time(now, hours=self._hours) - now).total_seconds())
            try:
                await asyncio.to_thread(self._pass)
            except Exception as exc:
                logger.exception("archive pass failed; waiting for the next slot")
                await asyncio.to_thread(self._alerts.publish, "odds-archive", f"archive pass failed: {exc}")
                continue
            # Inverting the fresh capture here keeps reads instant; readers never pay the fit.
            if self._engine.ready:
                try:
                    await self._engine.market_reach()
                except Exception:
                    logger.exception("implied-reach warm failed; the next read computes it")

    def _pass(self) -> None:
        asyncio.run(self._pass_async())

    async def _pass_async(self) -> None:
        odds = TheOddsApiClient(self._settings.odds_api_key)
        polymarket = GammaPolymarketClient()
        try:
            await archive_pass(self._settings, odds=odds, polymarket=polymarket)
        finally:
            await odds.aclose()
            await polymarket.aclose()
